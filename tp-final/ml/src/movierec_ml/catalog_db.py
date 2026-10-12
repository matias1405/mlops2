"""Base de la app por ambiente (app_dev / app_prod): DDL compartido y catálogo.

- El gateway crea sus tablas al arrancar (DDL idempotente) y lee `catalog` y `onboarding_pool`.
- Airflow sincroniza `catalog` con el modelo de cada alias: las películas de gold/app_catalog (la única fuente
  del catálogo) que el índice del modelo cubre, y recalcula el pool de onboarding.
- No se guarda nada de los usuarios.
"""
import io
import os

ENV_ALIAS = {"dev": "dev", "prod": "production"}

# Pantalla inicial: N películas al azar de las POOL_SIZE más populares de todos los tiempos.
# "Popular" = rating ponderado bayesiano (fórmula del Top 250 de IMDb) entre las que tienen al menos
# POOL_MIN_VOTES votos: combina puntaje y cantidad de votos, así 9.0 con 20 votos no le gana a 8.4 con 30.000.
POOL_SIZE = 200
POOL_MIN_VOTES = 1000

DDL = """
CREATE TABLE IF NOT EXISTS catalog (
    movie_id      bigint PRIMARY KEY,
    title         text   NOT NULL,
    genres        text[] NOT NULL DEFAULT '{}',
    release_year  int,
    vote_average  real,
    vote_count    int,
    popularity    real,
    poster_path   text,
    model_version text   NOT NULL,
    synced_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS onboarding_pool (
    movie_id        bigint PRIMARY KEY REFERENCES catalog (movie_id) ON DELETE CASCADE,
    rank            int  NOT NULL,
    weighted_rating real NOT NULL
);

CREATE TABLE IF NOT EXISTS poster_cache (
    movie_id   bigint PRIMARY KEY,
    status     text NOT NULL CHECK (status IN ('cached', 'missing')),
    s3_key     text,
    fetched_at timestamptz NOT NULL DEFAULT now()
);
"""

COPY_COLUMNS = ["movie_id", "title", "genres", "release_year", "vote_average", "vote_count", "popularity",
                "poster_path", "model_version"]


def _pg_array(values) -> str:
    items = ['"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"' for v in values]
    return "{" + ",".join(items) + "}"


def build_catalog(app_catalog, movie_ids, model_version: str):
    """Catálogo del ambiente = las películas de gold/app_catalog que cubre el índice del modelo."""
    import pandas as pd

    df = app_catalog[app_catalog["id"].isin(set(int(m) for m in movie_ids))].copy()
    df = df.rename(columns={"id": "movie_id"})
    df["model_version"] = str(model_version)
    df["genres"] = df["genres"].map(lambda g: list(g) if g is not None else [])
    df["release_year"] = pd.array(df["release_year"], dtype="Int64")
    df["vote_count"] = pd.array(df["vote_count"], dtype="Int64")
    return df[COPY_COLUMNS]


def build_onboarding_pool(catalog, size: int = POOL_SIZE, min_votes: int = POOL_MIN_VOTES):
    """Top `size` por rating ponderado: WR = v/(v+m)·R + m/(v+m)·C, con m = min_votes y C = media del catálogo."""
    df = catalog.dropna(subset=["vote_count", "vote_average"])
    c = float(df["vote_average"].mean())
    eligible = df[df["vote_count"] >= min_votes].copy()
    v, r, m = eligible["vote_count"].astype(float), eligible["vote_average"].astype(float), float(min_votes)
    eligible["weighted_rating"] = v / (v + m) * r + m / (v + m) * c
    top = eligible.sort_values(["weighted_rating", "vote_count"], ascending=False).head(size)
    top = top.assign(rank=range(1, len(top) + 1))
    assert set(top["movie_id"]) <= set(catalog["movie_id"]), "el pool tiene que ser un subconjunto del catálogo"
    return top[["movie_id", "rank", "weighted_rating", "poster_path"]].reset_index(drop=True)


def write_catalog(conn, catalog) -> int:
    """Reemplaza el catálogo en una sola transacción (los lectores ven el viejo o el nuevo, nunca a medias)."""
    buf = io.StringIO()
    for row in catalog.itertuples(index=False):
        vals = []
        for col, v in zip(COPY_COLUMNS, row, strict=True):
            if col == "genres":
                vals.append(_pg_array(v))
            elif v is None or (not isinstance(v, (list, str)) and _isna(v)):
                vals.append("\\N")
            else:
                vals.append(str(v).replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", " "))
        buf.write("\t".join(vals) + "\n")
    pool = build_onboarding_pool(catalog)
    with conn.transaction():
        conn.execute(DDL)
        conn.execute("TRUNCATE catalog CASCADE")
        with conn.cursor().copy(f"COPY catalog ({', '.join(COPY_COLUMNS)}) FROM STDIN") as copy:
            copy.write(buf.getvalue())
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO onboarding_pool (movie_id, rank, weighted_rating) VALUES (%s, %s, %s)",
                            [(int(r.movie_id), int(r.rank), float(r.weighted_rating)) for r in pool.itertuples()])
    return len(catalog)


def warm_posters(conn, catalog, size: str = "w342", workers: int = 8) -> dict:
    """Precarga en MinIO los posters del pool de onboarding que todavía no están (mismo layout que el gateway)."""
    from concurrent.futures import ThreadPoolExecutor

    import requests

    from .dataops import lake

    pool = build_onboarding_pool(catalog)
    cached = {r[0] for r in conn.execute("SELECT movie_id FROM poster_cache WHERE movie_id = ANY(%s)",
                                         ([int(x) for x in pool["movie_id"]],)).fetchall()}
    todo = [r for r in pool.itertuples() if int(r.movie_id) not in cached]
    s3 = lake.s3_client()

    def fetch(row):
        if not row.poster_path:
            return int(row.movie_id), "missing", None
        resp = requests.get(f"https://image.tmdb.org/t/p/{size}{row.poster_path}", timeout=15)
        if resp.status_code == 404:
            return int(row.movie_id), "missing", None
        resp.raise_for_status()
        key = f"{size}/{int(row.movie_id)}.jpg"
        s3.put_object(Bucket="posters", Key=key, Body=resp.content, ContentType="image/jpeg",
                      CacheControl="public, max-age=31536000, immutable")
        return int(row.movie_id), "cached", key

    results, errors = [], 0
    with ThreadPoolExecutor(workers) as ex:
        for fut in [ex.submit(fetch, r) for r in todo]:
            try:
                results.append(fut.result())
            except Exception as exc:  # un poster que falla no frena la sincronización
                errors += 1
                print(f"poster no precargado: {exc}")
    with conn.transaction():
        conn.cursor().executemany(
            """INSERT INTO poster_cache (movie_id, status, s3_key) VALUES (%s, %s, %s)
               ON CONFLICT (movie_id) DO UPDATE SET status = EXCLUDED.status, s3_key = EXCLUDED.s3_key, fetched_at = now()""",
            results)
    return {"pool": len(pool), "already_cached": len(cached), "fetched": len(results), "errors": errors}


def _isna(v) -> bool:
    try:
        import pandas as pd

        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def sync_catalog(env: str) -> dict:
    """Sincroniza app_<env>.catalog con el modelo del alias del ambiente (corre en el venv de Airflow)."""
    import mlflow
    import numpy as np
    import psycopg
    from mlflow import MlflowClient

    from .dataops.pipeline import load_gold
    from .training.pipeline import MODEL_NAME

    alias = ENV_ALIAS[env]
    mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, alias)
    ids_path = mlflow.artifacts.download_artifacts(run_id=mv.run_id, artifact_path="movierec/artifacts/bundle/movie_ids.npy")
    catalog = build_catalog(load_gold("app_catalog"), np.load(ids_path), mv.version)

    with psycopg.connect(app_dsn(env)) as conn:
        rows = write_catalog(conn, catalog)
        posters = warm_posters(conn, catalog)
    return {"env": env, "alias": alias, "model_version": str(mv.version), "rows": rows,
            "onboarding_posters": posters}


def app_dsn(env: str) -> str:
    db = f"app_{env}"
    return (f"host={os.environ.get('APP_DB_HOST', 'postgres')} dbname={db} user={db} "
            f"password={os.environ[f'APP_{env.upper()}_DB_PASSWORD']}")

