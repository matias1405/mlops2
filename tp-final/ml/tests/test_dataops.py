import pandas as pd
import pandera.errors as pe
import pytest

from movierec_ml.dataops.schemas import (
    RAW_COLUMNS,
    bronze_schema,
    gold_app_catalog_schema,
    gold_training_schema,
    silver_schema,
)
from movierec_ml.dataops.transform import (
    APP_CATALOG_COLUMNS,
    TRAINING_COLUMNS,
    build_app_catalog,
    build_training,
    clean,
    parse_list,
)


@pytest.fixture(scope="module")
def silver(raw_sample):
    return clean(raw_sample)[0]


def test_read_raw_solo_columnas_necesarias(raw_sample):
    assert list(raw_sample.columns) == RAW_COLUMNS
    assert len(raw_sample) == 5000


def test_sample_cumple_contrato_bronze(raw_sample):
    bronze_schema.validate(raw_sample, lazy=True)


def test_bronze_rechaza_rangos_invalidos(raw_sample):
    bad = raw_sample.head(3).copy()
    bad.loc[bad.index[0], "vote_average"] = 15.0
    with pytest.raises(pe.SchemaErrors):
        bronze_schema.validate(bad, lazy=True)


@pytest.mark.parametrize("value,expected", [
    ("Action, Science Fiction", ["Action", "Science Fiction"]),
    ("Drama", ["Drama"]),
    ("", []),
    (None, []),
    (float("nan"), []),
])
def test_parse_list(value, expected):
    assert parse_list(value) == expected


def test_silver_sin_filtro_de_votos_y_con_columnas_nuevas(raw_sample, silver):
    silver_schema.validate(silver, lazy=True)
    assert silver["id"].is_unique
    assert all(isinstance(c, list) for c in silver["production_companies"])
    assert {"budget", "production_companies", "imdb_id"} <= set(silver.columns)
    assert (silver["budget"].dropna() > 0).all()          # 0 en el crudo -> nulo


def test_clean_descarta_no_released_adult_y_duplicados():
    base = dict(title="T", original_title="T", tagline=None, genres="Drama", keywords="k", production_companies="A, B",
                original_language="EN", vote_average=7.0, popularity=1.0, release_date="2000-01-01", runtime=90.0,
                budget=0.0, imdb_id="tt1", poster_path="/p.jpg")
    raw = pd.DataFrame([
        {**base, "id": 1, "overview": "ok", "vote_count": 100, "status": "Released", "adult": False},
        {**base, "id": 1, "overview": "dup", "vote_count": 10, "status": "Released", "adult": False},
        {**base, "id": 2, "overview": "ok", "vote_count": 1, "status": "Rumored", "adult": False},
        {**base, "id": 3, "overview": "ok", "vote_count": 100, "status": "Released", "adult": True},
        {**base, "id": 4, "overview": "  ", "vote_count": 100, "status": "Released", "adult": False},
        {**base, "id": 5, "overview": "ok", "vote_count": 0, "status": "Released", "adult": False},
    ])
    silver, funnel = clean(raw)
    assert silver["id"].tolist() == [1, 5]                 # silver no filtra por votos
    assert silver.loc[0, "overview"] == "ok"               # se queda con la fila de más votos
    assert silver.loc[0, "original_language"] == "en"
    assert silver.loc[0, "production_companies"] == ["A", "B"] and pd.isna(silver.loc[0, "budget"])
    assert funnel == {"raw": 6, "released": 5, "not_adult": 4, "with_overview": 3, "with_title": 3, "dedup_id": 2,
                      "valid_language": 2}


def test_runtime_negativo_advierte_en_bronze_y_se_anula_en_silver(raw_sample):
    raw = raw_sample.head(50).copy()
    raw.loc[raw.index[0], "runtime"] = -28.0
    with pytest.warns(UserWarning):
        bronze_schema.validate(raw, lazy=True)  # no falla: solo advierte
    silver, _ = clean(raw)
    assert silver["runtime"].isna().sum() >= 1 and (silver["runtime"].dropna() >= 0).all()


def test_anio_imposible_se_anula_en_silver(raw_sample):
    raw = raw_sample.head(20).copy()
    raw.loc[raw.index[0], "release_date"] = "1800-01-01"
    silver, _ = clean(raw)
    silver_schema.validate(silver, lazy=True)
    assert silver["release_year"].dropna().between(1870, 2100).all()


def test_gold_training_filtros_y_columnas(silver):
    training, funnel = build_training(silver, min_vote_count=1000)
    gold_training_schema(1000).validate(training, lazy=True)
    assert list(training.columns) == TRAINING_COLUMNS
    assert (training["vote_count"] > 1000).all()
    assert training["genres"].map(len).gt(0).all() and training["keywords"].map(len).gt(0).all()
    assert funnel["silver"] == len(silver) and funnel["vote_count_gt_1000"] == len(training)


def test_gold_app_catalog_es_subconjunto_de_training(silver):
    training, _ = build_training(silver, min_vote_count=10)
    app, funnel = build_app_catalog(training, silver, min_vote_count=2000)
    gold_app_catalog_schema(2000).validate(app, lazy=True)
    assert list(app.columns) == APP_CATALOG_COLUMNS
    assert set(app["id"]) <= set(training["id"]) and (app["vote_count"] >= 2000).all()
    assert 0 < len(app) < len(training) and funnel["in_training"] == len(training)


def test_gold_desde_silver_leido_de_parquet(silver, tmp_path):
    # En el pipeline real, gold se arma leyendo silver del lake: las listas vuelven como arrays de numpy.
    path = tmp_path / "silver.parquet"
    silver.to_parquet(path, index=False)
    back = pd.read_parquet(path)
    silver_schema.validate(back, lazy=True)
    training, _ = build_training(back, 10)
    gold_training_schema(10).validate(training, lazy=True)
    app, _ = build_app_catalog(training, back, 200)
    gold_app_catalog_schema(200).validate(app, lazy=True)
