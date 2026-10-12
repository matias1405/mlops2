"""Posters con cache-aside: la primera vez se bajan de TMDB y se guardan en MinIO; después se sirven desde ahí.

    poster_cache.status = cached  -> url /media/posters/<size>/<id>.jpg (nginx lo sirve desde MinIO)
    poster_cache.status = missing -> sin poster (no tiene poster_path o TMDB devolvió 404): no se reintenta
    sin fila                      -> se descarga (concurrencia acotada, timeout, advisory lock por película)
Errores transitorios (timeouts, 5xx) no se cachean: se reintentará en el próximo pedido.
"""
import asyncio
import logging

import httpx

log = logging.getLogger(__name__)


class PosterService:
    def __init__(self, repo, s3_put, http: httpx.AsyncClient, *, bucket: str, size: str, tmdb_base: str,
                 media_prefix: str, concurrency: int, timeout_s: float):
        self.repo, self.s3_put, self.http = repo, s3_put, http
        self.bucket, self.size, self.tmdb_base, self.media_prefix = bucket, size, tmdb_base.rstrip("/"), media_prefix
        self.semaphore = asyncio.Semaphore(concurrency)
        self.timeout_s = timeout_s
        self.stats = {"hit": 0, "miss_fetched": 0, "missing": 0, "error": 0}

    def key(self, movie_id: int) -> str:
        return f"{self.size}/{movie_id}.jpg"

    def url(self, movie_id: int) -> str:
        return f"{self.media_prefix}/{self.bucket}/{self.key(movie_id)}"

    async def resolve(self, movies: list[dict]) -> dict[int, str | None]:
        ids = [m["movie_id"] for m in movies]
        status = await self.repo.poster_status(ids)
        out: dict[int, str | None] = {}
        to_fetch = []
        for m in movies:
            st = status.get(m["movie_id"])
            if st and st[0] == "cached":
                out[m["movie_id"]] = self.url(m["movie_id"])
                self.stats["hit"] += 1
            elif st and st[0] == "missing":
                out[m["movie_id"]] = None
            else:
                to_fetch.append(m)
        if to_fetch:
            results = await asyncio.gather(*(self._fetch(m) for m in to_fetch))
            out.update(dict(zip([m["movie_id"] for m in to_fetch], results, strict=True)))
        return out

    async def _fetch(self, movie: dict) -> str | None:
        movie_id, path = movie["movie_id"], movie.get("poster_path")
        if not path:
            await self.repo.set_poster(movie_id, "missing", None)
            self.stats["missing"] += 1
            return None
        async with self.semaphore, self.repo.poster_lock(movie_id) as got:
            if not got:  # otro request lo está bajando: la URL va a existir en instantes
                return self.url(movie_id)
            try:
                resp = await self.http.get(f"{self.tmdb_base}/{self.size}{path}", timeout=self.timeout_s)
            except httpx.HTTPError as exc:
                log.warning("poster %s: error transitorio %s", movie_id, exc)
                self.stats["error"] += 1
                return None
            if resp.status_code == 404:
                await self.repo.set_poster(movie_id, "missing", None)
                self.stats["missing"] += 1
                return None
            if resp.status_code != 200:
                log.warning("poster %s: TMDB respondió %s", movie_id, resp.status_code)
                self.stats["error"] += 1
                return None
            await self.s3_put(self.key(movie_id), resp.content, resp.headers.get("content-type", "image/jpeg"))
            await self.repo.set_poster(movie_id, "cached", self.key(movie_id))
            self.stats["miss_fetched"] += 1
            return self.url(movie_id)


def make_s3_put(endpoint: str, access_key: str, secret_key: str, bucket: str):
    import boto3

    client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key)

    async def put(key: str, body: bytes, content_type: str) -> None:
        await asyncio.to_thread(client.put_object, Bucket=bucket, Key=key, Body=body, ContentType=content_type,
                                CacheControl="public, max-age=31536000, immutable")

    return put
