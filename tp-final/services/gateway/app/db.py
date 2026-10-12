"""Acceso a la base del ambiente (catalog, onboarding_pool, poster_cache)."""
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from movierec_ml.catalog_db import DDL

MOVIE_COLUMNS = "movie_id, title, genres, release_year, vote_average, vote_count, poster_path"


class Repository:
    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    async def init_schema(self) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(DDL)

    async def ping(self) -> bool:
        async with self.pool.connection() as conn:
            await conn.execute("SELECT 1")
        return True

    async def onboarding(self, n: int) -> list[dict]:
        """n películas al azar del pool de las más populares (lo calcula Airflow al sincronizar el catálogo)."""
        cols = ", ".join(f"c.{c.strip()}" for c in MOVIE_COLUMNS.split(","))
        async with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"SELECT {cols} FROM onboarding_pool p JOIN catalog c USING (movie_id) "
                              "ORDER BY random() LIMIT %s", (n,))
            return await cur.fetchall()

    async def get_movies(self, ids: list[int]) -> dict[int, dict]:
        if not ids:
            return {}
        async with self.pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"SELECT {MOVIE_COLUMNS} FROM catalog WHERE movie_id = ANY(%s)", (ids,))
            return {r["movie_id"]: r for r in await cur.fetchall()}

    async def catalog_size(self) -> int:
        async with self.pool.connection() as conn:
            return (await (await conn.execute("SELECT count(*) FROM catalog")).fetchone())[0]

    async def poster_status(self, ids: list[int]) -> dict[int, tuple[str, str | None]]:
        if not ids:
            return {}
        async with self.pool.connection() as conn:
            cur = await conn.execute("SELECT movie_id, status, s3_key FROM poster_cache WHERE movie_id = ANY(%s)", (ids,))
            return {m: (s, k) for m, s, k in await cur.fetchall()}

    async def set_poster(self, movie_id: int, status: str, s3_key: str | None) -> None:
        async with self.pool.connection() as conn:
            await conn.execute(
                """INSERT INTO poster_cache (movie_id, status, s3_key) VALUES (%s, %s, %s)
                   ON CONFLICT (movie_id) DO UPDATE SET status = EXCLUDED.status, s3_key = EXCLUDED.s3_key,
                                                        fetched_at = now()""",
                (movie_id, status, s3_key))

    @asynccontextmanager
    async def poster_lock(self, movie_id: int):
        """Advisory lock por película: si dos requests piden el mismo poster nuevo, solo uno lo descarga."""
        async with self.pool.connection() as conn:
            got = (await (await conn.execute("SELECT pg_try_advisory_lock(%s)", (movie_id,))).fetchone())[0]
            try:
                yield got
            finally:
                if got:
                    await conn.execute("SELECT pg_advisory_unlock(%s)", (movie_id,))
