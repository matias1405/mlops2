"""Pasos de los DAGs de datos. Cada uno lee/escribe en el lake y devuelve metadatos chicos (XCom).

    download_tmdb:  bronze_is_empty -> download_to_bronze           (una sola vez)
    ingest_tmdb:    validate_bronze -> build_silver -> build_gold

Layout en el lake (rutas fijas: re-ingestar sobrescribe silver y gold; bronze no se toca):
    bronze/tmdb/TMDB_movie_dataset_v11.csv      dataset crudo, tal cual se bajó
    silver/tmdb/movies.parquet                  dataset limpio y tipado, sin uso en mente
    gold/training/movies.parquet                lo que necesita el modelo
    gold/app_catalog/movies.parquet             lo que la plataforma puede recomendar y mostrar
"""
import tempfile
from pathlib import Path

from . import DATASET_FILE, lake, sources

BRONZE_KEY = f"tmdb/{DATASET_FILE}"
SILVER_KEY = "tmdb/movies.parquet"
GOLD_KEYS = {"training": "training/movies.parquet", "app_catalog": "app_catalog/movies.parquet"}
# Umbrales fijos: el entrenamiento usa todas las películas con más de 10 votos y la plataforma recomienda solo
# las de al menos 200 (siempre un subconjunto del entrenamiento y que contiene al pool de onboarding).
TRAINING_MIN_VOTE_COUNT = 10
APP_MIN_VOTE_COUNT = 200


def bronze_is_empty() -> bool:
    """False si bronze ya tiene el dataset: la descarga es única y no se repite."""
    if lake.exists(lake.s3_client(), lake.BRONZE, BRONZE_KEY):
        print(f"bronze/{BRONZE_KEY} ya existe: no se vuelve a bajar")
        return False
    return True


def download_to_bronze(source: str = "kaggle") -> dict:
    """Sube el CSV a bronze sin sobrescribir nunca (versión de Kaggle vigente al momento de bajarlo)."""
    s3 = lake.s3_client()
    if lake.exists(s3, lake.BRONZE, BRONZE_KEY):
        raise RuntimeError("bronze ya tiene datos: para bajar otra versión hay que vaciar bronze a mano")
    with tempfile.TemporaryDirectory(prefix="movierec-bronze-") as tmp:
        if source == "kaggle":
            meta = sources.kaggle_metadata()
            path = sources.download_kaggle(meta, Path(tmp) / DATASET_FILE)
        else:
            meta, path = sources.local_file(source)
        s3.upload_file(str(path), lake.BRONZE, BRONZE_KEY)
    return {"source": meta["source"], "version": meta["version"], "size_bytes": meta["size_bytes"],
            "key": f"{lake.BRONZE}/{BRONZE_KEY}"}


def _read_bronze():
    from .transform import read_raw

    s3 = lake.s3_client()
    if not lake.exists(s3, lake.BRONZE, BRONZE_KEY):
        raise RuntimeError("bronze está vacío: corré primero el DAG download_tmdb")
    return read_raw(lake.download_cached(s3, lake.BRONZE, BRONZE_KEY))


def validate_bronze() -> dict:
    import pandera.errors as pe

    from .schemas import bronze_schema

    raw, skipped = _read_bronze()
    try:
        bronze_schema.validate(raw, lazy=True)
    except pe.SchemaErrors as exc:
        cases = exc.failure_cases
        print(cases.head(50).to_string())
        raise RuntimeError(f"bronze no cumple el contrato tmdb_bronze: {len(cases)} fallas (detalle arriba)") from exc
    return {"rows": len(raw), "skipped_malformed_rows": skipped}


def build_silver() -> dict:
    from .schemas import silver_schema
    from .transform import clean

    raw, _ = _read_bronze()
    silver, funnel = clean(raw)
    silver = silver_schema.validate(silver, lazy=True)
    lake.put_parquet(lake.s3_client(), silver, lake.SILVER, SILVER_KEY)
    print(f"embudo bronze -> silver: {funnel}")
    return {"rows": len(silver), "key": f"{lake.SILVER}/{SILVER_KEY}"}


def build_gold(training_min_vote_count: int = TRAINING_MIN_VOTE_COUNT,
               app_min_vote_count: int = APP_MIN_VOTE_COUNT) -> dict:
    """Gold training y gold app_catalog desde silver."""
    import pandas as pd

    from ..catalog_db import POOL_MIN_VOTES
    from .schemas import gold_app_catalog_schema, gold_training_schema
    from .transform import build_app_catalog, build_training

    if app_min_vote_count < training_min_vote_count:
        raise ValueError(f"app_min_vote_count ({app_min_vote_count}) < training_min_vote_count "
                         f"({training_min_vote_count}): app_catalog tiene que ser un subconjunto de training")
    if app_min_vote_count > POOL_MIN_VOTES:
        raise ValueError(f"app_min_vote_count ({app_min_vote_count}) > POOL_MIN_VOTES ({POOL_MIN_VOTES}): "
                         "el pool de onboarding tiene que ser un subconjunto de app_catalog")
    s3 = lake.s3_client()
    silver = pd.read_parquet(lake.download_cached(s3, lake.SILVER, SILVER_KEY))

    training, funnel_t = build_training(silver, training_min_vote_count)
    training = gold_training_schema(training_min_vote_count).validate(training, lazy=True)
    app, funnel_a = build_app_catalog(training, silver, app_min_vote_count)
    app = gold_app_catalog_schema(app_min_vote_count).validate(app, lazy=True)
    assert set(app["id"]) <= set(training["id"]), "app_catalog no es subconjunto de training"

    lake.put_parquet(s3, training, lake.GOLD, GOLD_KEYS["training"])
    lake.put_parquet(s3, app, lake.GOLD, GOLD_KEYS["app_catalog"])
    print(f"embudo silver -> training: {funnel_t}; training -> app_catalog: {funnel_a}")
    return {"training_rows": len(training), "app_catalog_rows": len(app)}


def load_gold(dataset: str):
    """DataFrame de gold training o app_catalog."""
    import pandas as pd

    s3 = lake.s3_client()
    return pd.read_parquet(lake.download_cached(s3, lake.GOLD, GOLD_KEYS[dataset]))
