import time
from contextlib import asynccontextmanager

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import main
from app.auth import TokenVerifier
from app.posters import PosterService
from app.recommender import RecommenderUnavailable

ISSUER = "http://localhost:8180/realms/movierec"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TMDB = "https://image.tmdb.org/t/p"

CATALOG = {
    862: {"movie_id": 862, "title": "Toy Story", "genres": ["Animation"], "release_year": 1995, "vote_average": 8.0,
          "vote_count": 17000, "poster_path": "/toy.jpg"},
    808: {"movie_id": 808, "title": "Shrek", "genres": ["Animation"], "release_year": 2001, "vote_average": 7.7,
          "vote_count": 16000, "poster_path": "/shrek.jpg"},
    10: {"movie_id": 10, "title": "Sin poster", "genres": ["Drama"], "release_year": 2000, "vote_average": 6.0,
         "vote_count": 100, "poster_path": None},
    11: {"movie_id": 11, "title": "Poster borrado", "genres": ["Drama"], "release_year": 2000, "vote_average": 6.0,
         "vote_count": 90, "poster_path": "/gone.jpg"},
}


class FakeJwks:
    class _K:
        key = KEY.public_key()

    def get_signing_key_from_jwt(self, token):
        return self._K()


def token(roles=("movierec-user",), iss=ISSUER, azp="movierec-web", sub="user-123"):
    return jwt.encode({"iss": iss, "sub": sub, "exp": int(time.time()) + 300, "azp": azp, "roles": list(roles),
                       "preferred_username": "client_user"}, KEY, algorithm="RS256")


class FakeRepo:
    def __init__(self):
        self.posters = {}

    async def ping(self):
        return True

    async def catalog_size(self):
        return len(CATALOG)

    async def onboarding(self, n):
        import random

        pool = [m for m in CATALOG.values() if m["vote_count"] >= 1000]  # el pool lo calcula Airflow
        return random.sample(pool, min(n, len(pool)))

    async def get_movies(self, ids):
        return {i: CATALOG[i] for i in ids if i in CATALOG}

    async def poster_status(self, ids):
        return {i: self.posters[i] for i in ids if i in self.posters}

    async def set_poster(self, movie_id, status, key):
        self.posters[movie_id] = (status, key)

    @asynccontextmanager
    async def poster_lock(self, movie_id):
        yield True



class FakeRecommender:
    def __init__(self):
        self.down = False

    async def recommend(self, movie_ids, k):
        if self.down:
            raise RecommenderUnavailable("UNAVAILABLE: test")
        recs = [(808, 2.9, 862), (10, 2.5, 862), (11, 2.1, 862), (999, 1.8, 862)][:k]  # 999 fuera del catálogo
        return [r for r in recs if r[0] not in movie_ids], [5555] if 5555 in movie_ids else [], {
            "alias": "production", "version": "7", "config": "v2", "contract_version": 2}

    async def model_info(self):
        return {"alias": "production", "version": "7", "config": "v2", "contract_version": 2}


@pytest.fixture
def client():
    repo, s3 = FakeRepo(), []

    async def s3_put(key, body, content_type):
        s3.append(key)

    http = httpx.AsyncClient()
    main.app.state.repo = repo
    main.app.state.recommender = FakeRecommender()
    main.app.state.verifier = TokenVerifier(ISSUER, "unused", {"movierec-web"}, {"movierec-user"}, jwks_client=FakeJwks())
    main.app.state.posters = PosterService(repo, s3_put, http, bucket="posters", size="w342", tmdb_base=TMDB,
                                           media_prefix="/media", concurrency=4, timeout_s=2)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c, repo, s3
    main.app.state.repo = None


def auth(t=None):
    return {"Authorization": f"Bearer {t or token()}"}


def test_health_sin_auth(client):
    c, _, _ = client
    body = c.get("/api/health").json()
    assert body["status"] == "ok" and body["db"]["catalog_movies"] == 4 and body["model"]["version"] == "7"


@pytest.mark.parametrize("headers,code", [
    ({}, 401),
    ({"Authorization": "Bearer basura"}, 401),
    (auth(token(iss="http://localhost:8180/realms/platform")), 401),   # token de otro realm (otro ambiente)
    (auth(token(azp="otro-client")), 401),
    (auth(token(roles=("app-developer",))), 403),
])
def test_auth(client, headers, code):
    c, _, _ = client
    assert c.get("/api/movies/onboarding", params={"n": 2}, headers=headers).status_code == code


@respx.mock
def test_onboarding_con_poster_cache_aside(client):
    c, repo, s3 = client
    routes = [respx.get(f"{TMDB}/w342/{p}.jpg").mock(return_value=httpx.Response(200, content=b"jpg",
                                                                                  headers={"content-type": "image/jpeg"}))
              for p in ("toy", "shrek")]
    r = c.get("/api/movies/onboarding", params={"n": 2}, headers=auth()).json()
    urls = {i["movie_id"]: i["poster_url"] for i in r["items"]}
    assert urls[862] == "/media/posters/w342/862.jpg" and sorted(s3) == ["w342/808.jpg", "w342/862.jpg"]
    c.get("/api/movies/onboarding", params={"n": 2}, headers=auth())
    assert [rt.call_count for rt in routes] == [1, 1]  # segunda vez sale del cache: no se llama a TMDB


@respx.mock
def test_recomendaciones_enriquecidas_y_posters(client):
    c, repo, s3 = client
    shrek = respx.get(f"{TMDB}/w342/shrek.jpg").mock(return_value=httpx.Response(200, content=b"x"))
    gone = respx.get(f"{TMDB}/w342/gone.jpg").mock(return_value=httpx.Response(404))
    body = {"movie_ids": [862, 5555, 1, 2, 3], "k": 4}
    r = c.post("/api/recommendations", json=body, headers=auth()).json()
    items = {i["movie_id"]: i for i in r["items"]}
    assert list(items) == [808, 10, 11]                     # 999 (fuera del catálogo) se omite
    assert items[808]["poster_url"] == "/media/posters/w342/808.jpg"
    assert items[10]["poster_url"] is None and items[11]["poster_url"] is None
    assert repo.posters[10] == ("missing", None) and repo.posters[11] == ("missing", None)  # cache negativo
    assert r["unknown_movie_ids"] == [5555] and r["model"]["version"] == "7"
    assert items[808]["because_of"] == {"movie_id": 862, "title": "Toy Story"}
    c.post("/api/recommendations", json=body, headers=auth())
    assert shrek.call_count == 1 and gone.call_count == 1   # ni el hit ni el 404 se vuelven a pedir


@pytest.mark.parametrize("body", [{"movie_ids": []}, {"movie_ids": [1, 2, 3, 4]}, {"movie_ids": [1, 2, 3, 4, 5, 6]},
                                  {"movie_ids": [1, 2, 3, 4, 5], "k": 0}, {"movie_ids": [1, 2, 3, 4, 5], "k": 51}])
def test_validacion(client, body):
    c, _, _ = client
    assert c.post("/api/recommendations", json=body, headers=auth()).status_code == 422


def test_recommender_caido_503(client):
    c, _, _ = client
    main.app.state.recommender.down = True
    assert c.post("/api/recommendations", json={"movie_ids": [862, 808, 10, 11, 1]}, headers=auth()).status_code == 503


@respx.mock
def test_onboarding_al_azar_del_pool(client):
    c, _, _ = client
    respx.get(url__regex=rf"{TMDB}/w342/.*").mock(return_value=httpx.Response(200, content=b"x"))
    r = c.get("/api/movies/onboarding", params={"n": 2}, headers=auth())
    assert r.status_code == 200
    ids = {i["movie_id"] for i in r.json()["items"]}
    assert ids <= {862, 808} and len(ids) == 2 and all(i["poster_url"] for i in r.json()["items"])
    assert c.get("/api/movies/onboarding", params={"n": 100}, headers=auth()).status_code == 422
    assert c.get("/api/movies/onboarding").status_code == 401
