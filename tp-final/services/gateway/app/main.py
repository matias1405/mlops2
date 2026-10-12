"""api-gateway (FastAPI): único punto de entrada del frontend del ambiente.

    GET  /api/health                 estado (sin auth): base, catálogo y modelo servido
    GET  /api/me                     usuario autenticado
    GET  /api/model                  modelo servido por el recommender del ambiente
    GET  /api/movies/onboarding?n=   n películas al azar de las 200 más populares (pantalla inicial)
    POST /api/recommendations        recomendaciones de día 0 a partir de las 5 películas elegidas

No se guarda nada de los usuarios: la API solo lee el catálogo y pide recomendaciones.
"""
import logging
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .auth import TokenVerifier, User, current_user
from .config import Settings
from .recommender import RecommenderClient, RecommenderUnavailable

log = logging.getLogger("gateway")
settings = Settings()


def _rate_key(request: Request) -> str:
    # Por token (usuario) si viene; si no, por IP.
    return request.headers.get("authorization", "")[-32:] or get_remote_address(request)


limiter = Limiter(key_func=_rate_key)


class RecommendationRequest(BaseModel):
    # Exactamente settings.required_picks películas elegidas (el onboarding no recomienda con menos).
    movie_ids: list[int] = Field(min_length=settings.required_picks, max_length=settings.required_picks)
    k: int = Field(10, ge=1, le=settings.max_k)



def _movie_out(m: dict, poster_url: str | None, score: float | None = None) -> dict:
    out = {"movie_id": m["movie_id"], "title": m["title"], "genres": list(m["genres"] or []),
           "release_year": m["release_year"], "vote_average": m["vote_average"], "poster_url": poster_url}
    if score is not None:
        out["score"] = round(score, 4)
    return out


async def _default_dependencies(app: FastAPI):
    """Dependencias reales (en tests se reemplazan por fakes vía app.state antes de arrancar)."""
    from psycopg_pool import AsyncConnectionPool

    from .db import Repository
    from .posters import PosterService, make_s3_put

    pool = AsyncConnectionPool(settings.db_dsn, min_size=2, max_size=settings.poster_concurrency * 2 + 5, open=False)
    await pool.open(wait=True, timeout=60)
    repo = Repository(pool)
    await repo.init_schema()
    http = httpx.AsyncClient(follow_redirects=True)
    app.state.repo = repo
    app.state.recommender = RecommenderClient(settings.recommender_target)
    app.state.verifier = TokenVerifier(settings.auth_issuer, settings.jwks_url, settings.allowed_clients,
                                       settings.required_roles)
    app.state.posters = PosterService(
        repo, make_s3_put(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.poster_bucket),
        http, bucket=settings.poster_bucket, size=settings.poster_size, tmdb_base=settings.tmdb_image_base,
        media_prefix=settings.public_media_prefix, concurrency=settings.poster_concurrency,
        timeout_s=settings.poster_timeout_s)

    async def close():
        await http.aclose()
        await app.state.recommender.close()
        await pool.close()

    return close


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    close = None
    if not getattr(app.state, "repo", None):
        close = await _default_dependencies(app)
    log.info("api-gateway %s listo (issuer %s)", settings.env_name, settings.auth_issuer)
    yield
    if close:
        await close()


app = FastAPI(title=f"movierec api-gateway ({settings.env_name})", lifespan=lifespan,
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/api/health")
async def health(request: Request):
    st = request.app.state
    out = {"env": settings.env_name, "status": "ok"}
    try:
        await st.repo.ping()
        out["db"] = {"ok": True, "catalog_movies": await st.repo.catalog_size()}
    except Exception as exc:  # el health informa, no falla
        out["db"], out["status"] = {"ok": False, "error": str(exc)}, "degraded"
    try:
        info = await st.recommender.model_info()
        out["model"] = {k: info[k] for k in ("alias", "version", "config", "contract_version")}
        if not info["version"]:
            out["status"] = "degraded"
    except RecommenderUnavailable as exc:
        out["model"], out["status"] = {"error": str(exc)}, "degraded"
    out["posters"] = st.posters.stats
    return out


@app.get("/api/me")
async def me(user: User = Depends(current_user)):
    return {"username": user.username, "roles": sorted(user.roles), "client": user.client, "env": settings.env_name}


@app.get("/api/model")
async def model(request: Request, user: User = Depends(current_user)):
    try:
        return await request.app.state.recommender.model_info()
    except RecommenderUnavailable as exc:
        raise HTTPException(503, f"recommender no disponible: {exc}") from exc


@app.get("/api/movies/onboarding")
async def onboarding(request: Request, n: int = Query(24, ge=1, le=48), user: User = Depends(current_user)):
    st = request.app.state
    movies = await st.repo.onboarding(n)
    posters = await st.posters.resolve(movies)
    return {"items": [_movie_out(m, posters.get(m["movie_id"])) for m in movies]}


@app.post("/api/recommendations")
@limiter.limit(settings.rate_limit)
async def recommendations(request: Request, body: RecommendationRequest, user: User = Depends(current_user)):
    st = request.app.state
    started = time.perf_counter()
    try:
        items, unknown, info = await st.recommender.recommend(body.movie_ids, body.k)
    except RecommenderUnavailable as exc:
        raise HTTPException(503, f"recommender no disponible: {exc}") from exc
    movies = await st.repo.get_movies(list({m for m, _, _ in items} | set(body.movie_ids)))
    # ids fuera del catálogo del ambiente se omiten
    ordered = [(movies[m], s, b) for m, s, b in items if m in movies]
    posters = await st.posters.resolve([m for m, _, _ in ordered])
    latency_ms = int((time.perf_counter() - started) * 1000)  # informativa: no se guarda
    return {
        "items": [{**_movie_out(m, posters.get(m["movie_id"]), s),
                   "because_of": {"movie_id": b, "title": movies[b]["title"] if b in movies else None}}
                  for m, s, b in ordered],
        "unknown_movie_ids": unknown,
        "model": {"alias": info["alias"], "version": info["version"], "config": info["config"]},
        "latency_ms": latency_ms,
    }

