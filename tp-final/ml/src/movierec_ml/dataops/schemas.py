"""Contratos de datos (pandera) de cada capa del lake.

- bronze: el CSV crudo tiene las columnas y tipos esperados y rangos plausibles. No exige calidad de
  negocio (duplicados, overview vacío, etc.): eso lo resuelve la limpieza.
- silver: dato limpio y tipado, sin uso en mente (ids únicos, listas parseadas, sin filtro de votos).
- gold training: lo que necesita el modelo (listas de texto no vacías, vote_count > umbral).
- gold app_catalog: lo que muestra la plataforma (columnas de la UI, vote_count >= umbral).
"""
import numpy as np
from pandera.pandas import Check, Column, DataFrameSchema

# Columnas que se leen del CSV crudo (el resto se descarta en la lectura para ahorrar memoria).
RAW_COLUMNS = [
    "id", "title", "original_title", "overview", "tagline", "genres", "keywords", "production_companies",
    "original_language", "vote_average", "vote_count", "popularity", "status", "release_date", "runtime",
    "budget", "imdb_id", "adult", "poster_path",
]

STATUSES = ["Released", "Rumored", "Post Production", "In Production", "Planned", "Canceled"]


def _is_list(non_empty: bool = False) -> Check:
    """Lista (en memoria) o array de numpy (leída desde parquet)."""
    def ok(v) -> bool:
        return isinstance(v, (list, np.ndarray)) and (len(v) > 0 or not non_empty)

    return Check(lambda s: s.map(ok), element_wise=False, error="lista no vacía" if non_empty else "lista")


bronze_schema = DataFrameSchema(
    {
        "id": Column(int, Check.ge(1)),
        "title": Column(str, nullable=True),
        "original_title": Column(str, nullable=True),
        "overview": Column(str, nullable=True),
        "tagline": Column(str, nullable=True),
        "genres": Column(str, nullable=True),
        "keywords": Column(str, nullable=True),
        "production_companies": Column(str, nullable=True),
        "original_language": Column(str, nullable=True),
        "vote_average": Column(float, Check.in_range(0, 10), nullable=True),
        "vote_count": Column(int, Check.ge(0)),
        "popularity": Column(float, Check.ge(0), nullable=True),
        "status": Column(str, Check.isin(STATUSES), nullable=True),
        "release_date": Column(str, nullable=True),
        # Calidad de negocio, no estructura: se advierte y se corrige en silver (runtime < 0 -> nulo).
        "runtime": Column(float, Check.ge(0, raise_warning=True), nullable=True),
        "budget": Column(float, Check.ge(0, raise_warning=True), nullable=True),
        "imdb_id": Column(str, nullable=True),
        "adult": Column(bool),
        "poster_path": Column(str, nullable=True),
    },
    strict=True,
    coerce=True,
    name="tmdb_bronze",
)

silver_schema = DataFrameSchema(
    {
        "id": Column(int, Check.ge(1), unique=True),
        "title": Column(str, Check.str_length(min_value=1)),
        "overview": Column(str, Check.str_length(min_value=1)),
        "tagline": Column(str, nullable=True),
        "genres": Column(object, _is_list()),
        "keywords": Column(object, _is_list()),
        "production_companies": Column(object, _is_list()),
        "original_language": Column(str, Check.str_length(min_value=2, max_value=3)),
        "vote_average": Column(float, Check.in_range(0, 10)),
        "vote_count": Column(int, Check.ge(0)),
        "popularity": Column(float, Check.ge(0)),
        "release_year": Column("Int64", Check.in_range(1870, 2100), nullable=True),
        "runtime": Column(float, Check.ge(0), nullable=True),
        "budget": Column(float, Check.gt(0), nullable=True),  # 0 en el crudo = desconocido -> nulo
        "imdb_id": Column(str, nullable=True),
        "poster_path": Column(str, nullable=True),
    },
    strict=True,
    coerce=True,
    name="tmdb_silver",
)


def gold_training_schema(min_vote_count: int) -> DataFrameSchema:
    """`vote_count > min_vote_count` (estricto)."""
    return DataFrameSchema(
        {
            "id": Column(int, Check.ge(1), unique=True),
            "title": Column(str, Check.str_length(min_value=1)),
            "overview": Column(str, Check.str_length(min_value=1)),
            "tagline": Column(str, nullable=True),
            "keywords": Column(object, _is_list(non_empty=True)),
            "budget": Column(float, Check.gt(0), nullable=True),
            "release_year": Column("Int64", Check.in_range(1870, 2100), nullable=True),
            "original_language": Column(str, Check.str_length(min_value=2, max_value=3)),
            "genres": Column(object, _is_list(non_empty=True)),
            "production_companies": Column(object, _is_list()),
            "vote_count": Column(int, Check.gt(min_vote_count)),
        },
        strict=True,
        coerce=True,
        name="tmdb_gold_training",
    )


def gold_app_catalog_schema(min_vote_count: int) -> DataFrameSchema:
    """`vote_count >= min_vote_count`."""
    return DataFrameSchema(
        {
            "id": Column(int, Check.ge(1), unique=True),
            "title": Column(str, Check.str_length(min_value=1)),
            "poster_path": Column(str, nullable=True),
            "release_year": Column("Int64", Check.in_range(1870, 2100), nullable=True),
            "vote_average": Column(float, Check.in_range(0, 10)),
            "vote_count": Column(int, Check.ge(min_vote_count)),
            "popularity": Column(float, Check.ge(0)),
            "genres": Column(object, _is_list(non_empty=True)),
        },
        strict=True,
        coerce=True,
        name="tmdb_gold_app_catalog",
    )
