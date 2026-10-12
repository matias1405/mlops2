"""Lectura del CSV crudo, limpieza bronze -> silver y datasets gold por uso."""
from pathlib import Path

import pandas as pd

from .schemas import RAW_COLUMNS

STRING_COLUMNS = ["title", "original_title", "overview", "tagline", "genres", "keywords", "production_companies",
                  "original_language", "status", "release_date", "imdb_id", "poster_path"]
SILVER_COLUMNS = ["id", "title", "overview", "tagline", "genres", "keywords", "production_companies",
                  "original_language", "vote_average", "vote_count", "popularity", "release_year", "runtime",
                  "budget", "imdb_id", "poster_path"]
# Lo que usa el modelo (unión de las columnas de v1–v4) + vote_count para el contrato del umbral.
TRAINING_COLUMNS = ["id", "title", "overview", "tagline", "keywords", "budget", "release_year",
                    "original_language", "genres", "production_companies", "vote_count"]
# Lo que muestra la plataforma: tarjetas del gateway (_movie_out) y pool de onboarding.
APP_CATALOG_COLUMNS = ["id", "title", "poster_path", "release_year", "vote_average", "vote_count", "popularity",
                       "genres"]
YEAR_MIN, YEAR_MAX = 1870, 2100  # mismo rango que los contratos de silver y gold


def read_raw(path: Path) -> tuple[pd.DataFrame, int]:
    """Lee solo RAW_COLUMNS con pyarrow (los overview tienen saltos de línea dentro de comillas).

    Devuelve el DataFrame y la cantidad de filas mal formadas que se descartaron.
    """
    import pyarrow as pa
    import pyarrow.csv as pcsv

    skipped = 0

    def on_invalid(_row):
        nonlocal skipped
        skipped += 1
        return "skip"

    types = {c: pa.string() for c in STRING_COLUMNS}
    types.update({"id": pa.int64(), "vote_count": pa.int64(), "vote_average": pa.float64(),
                  "popularity": pa.float64(), "runtime": pa.float64(), "budget": pa.float64(), "adult": pa.bool_()})
    table = pcsv.read_csv(
        path,
        parse_options=pcsv.ParseOptions(newlines_in_values=True, invalid_row_handler=on_invalid),
        convert_options=pcsv.ConvertOptions(include_columns=RAW_COLUMNS, column_types=types,
                                            strings_can_be_null=True),
    )
    return table.to_pandas(), skipped


def parse_list(value) -> list[str]:
    """'Action, Science Fiction' -> ['Action', 'Science Fiction']; nulo -> []."""
    if not isinstance(value, str) or not value.strip():
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _blank(s: pd.Series) -> pd.Series:
    return s.fillna("").str.strip().str.len() == 0


def _plausible_year(year: pd.Series) -> pd.Series:
    """Años imposibles para una película (fechas mal cargadas, p.ej. 1800) -> nulo."""
    return year.where(year.between(YEAR_MIN, YEAR_MAX))


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Silver: solo filtros de calidad del dato (sin uso en mente: no filtra por votos)."""
    funnel = {"raw": len(raw)}
    df = raw[raw["status"] == "Released"]
    funnel["released"] = len(df)
    df = df[~df["adult"].fillna(False)]
    funnel["not_adult"] = len(df)
    df = df[~_blank(df["overview"])]
    funnel["with_overview"] = len(df)
    df = df[~_blank(df["title"])]
    funnel["with_title"] = len(df)
    df = df.sort_values("vote_count", ascending=False).drop_duplicates("id", keep="first")
    funnel["dedup_id"] = len(df)

    df = df.assign(
        overview=df["overview"].str.strip(),
        title=df["title"].str.strip(),
        tagline=df["tagline"].where(~_blank(df["tagline"])),
        genres=df["genres"].map(parse_list),
        keywords=df["keywords"].map(parse_list),
        production_companies=df["production_companies"].map(parse_list),
        original_language=df["original_language"].fillna("xx").str.lower().str.strip(),
        vote_average=df["vote_average"].fillna(0.0),
        popularity=df["popularity"].fillna(0.0),
        release_year=_plausible_year(pd.to_datetime(df["release_date"], errors="coerce").dt.year.astype("Int64")),
        runtime=df["runtime"].where(df["runtime"] >= 0),  # valores imposibles -> nulo
        budget=df["budget"].where(df["budget"] > 0),       # 0 = desconocido -> nulo
        imdb_id=df["imdb_id"].where(~_blank(df["imdb_id"])),
    )
    df = df[df["original_language"].str.len().between(2, 3)]
    funnel["valid_language"] = len(df)
    return df[SILVER_COLUMNS].reset_index(drop=True), funnel


def build_training(silver: pd.DataFrame, min_vote_count: int) -> tuple[pd.DataFrame, dict]:
    """Gold training: películas con texto y etiquetas completos y `vote_count > min_vote_count`."""
    funnel = {"silver": len(silver)}
    df = silver[silver["genres"].map(len) > 0]
    funnel["with_genres"] = len(df)
    df = df[df["keywords"].map(len) > 0]
    funnel["with_keywords"] = len(df)
    df = df[df["vote_count"] > min_vote_count]
    funnel[f"vote_count_gt_{min_vote_count}"] = len(df)
    return df[TRAINING_COLUMNS].reset_index(drop=True), funnel


def build_app_catalog(training: pd.DataFrame, silver: pd.DataFrame, min_vote_count: int) -> tuple[pd.DataFrame, dict]:
    """Gold app_catalog: subset recomendable (⊂ training, así toda película tiene embedding) con columnas de la UI."""
    df = silver[silver["id"].isin(training["id"])]
    funnel = {"in_training": len(df)}
    df = df[df["vote_count"] >= min_vote_count]
    funnel[f"vote_count_ge_{min_vote_count}"] = len(df)
    return df[APP_CATALOG_COLUMNS].reset_index(drop=True), funnel
