import json
import time
from pathlib import Path

import grpc
import jwt
import numpy as np
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from grpc_health.v1 import health_pb2, health_pb2_grpc

from app.auth import JwtValidator
from app.config import Settings
from app.server import build_server
from app.store import ModelStore
from movierec_ml import serving_bundle as sb
from movierec_ml.proto import recommender_pb2 as pb
from movierec_ml.proto import recommender_pb2_grpc as pb_grpc

ISSUER = "http://localhost:8180/realms/platform"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeJwks:
    class _K:
        key = KEY.public_key()

    def get_signing_key_from_jwt(self, token):
        return self._K()


def token(roles=("model-deployer",), iss=ISSUER, exp_in=300):
    return jwt.encode({"iss": iss, "exp": int(time.time()) + exp_in, "azp": "airflow-deployer", "roles": list(roles)},
                      KEY, algorithm="RS256")


def make_bundle(tmp: Path, n: int = 50, dim: int = 8, seed: int = 0, contract: int | None = None) -> dict:
    rng = np.random.default_rng(seed)
    emb = rng.normal(size=(n, dim)).astype(np.float32)
    emb /= np.linalg.norm(emb, axis=1, keepdims=True)
    path = sb.write_bundle(tmp, emb, np.arange(1000, 1000 + n), {"model_config": "test"})
    if contract is not None:
        man = json.loads((path / "manifest.json").read_text())
        man["contract_version"] = contract
        (path / "manifest.json").write_text(json.dumps(man))
    return path


class Registry:
    """Loader falso: simula models:/movierec@alias en MLflow."""

    def __init__(self):
        self.version, self.path = None, None

    def __call__(self, name, alias):
        if self.version is None:
            raise RuntimeError("alias inexistente")
        return self.version, sb.load_bundle(self.path)


@pytest.fixture
def env(tmp_path):
    registry = Registry()
    store = ModelStore("movierec", "dev", loader=registry)
    validator = JwtValidator(ISSUER, "unused", "model-deployer", jwks_client=FakeJwks())
    server, servicer, port = build_server(Settings(), store, validator, port=0)
    server.start()
    channel = grpc.insecure_channel(f"localhost:{port}")
    yield registry, store, pb_grpc.RecommenderStub(channel), health_pb2_grpc.HealthStub(channel), tmp_path
    channel.close()
    server.stop(None)


def serving(health_stub):
    return health_stub.Check(health_pb2.HealthCheckRequest(service="")).status == health_pb2.HealthCheckResponse.SERVING


def test_sin_modelo_not_serving_y_unavailable(env):
    _, _, stub, health_stub, _ = env
    assert not serving(health_stub)
    with pytest.raises(grpc.RpcError) as e:
        stub.Recommend(pb.RecommendRequest(movie_ids=[1000], k=5))
    assert e.value.code() == grpc.StatusCode.UNAVAILABLE


def test_recommend_excluye_semillas_y_coincide_con_numpy(env):
    registry, store, stub, health_stub, tmp = env
    registry.version, registry.path = "1", make_bundle(tmp / "v1")
    stub.Reload(pb.ReloadRequest(), metadata=[("authorization", f"Bearer {token()}")])
    assert serving(health_stub)
    resp = stub.Recommend(pb.RecommendRequest(movie_ids=[1000, 1001, 999999], k=5))
    ids = [r.movie_id for r in resp.items]
    assert len(ids) == 5 and not {1000, 1001} & set(ids)
    assert list(resp.unknown_movie_ids) == [999999]
    assert [r.score for r in resp.items] == sorted([r.score for r in resp.items], reverse=True)
    bundle = sb.load_bundle(registry.path)
    expected = sb.recommend_per_seed(bundle["embeddings"], [0, 1], 5)   # filas de 1000 y 1001
    assert ids == [int(bundle["movie_ids"][r]) for r, _, _ in expected]
    assert {r.because_of for r in resp.items} <= {1000, 1001}
    assert resp.model.version == "1" and resp.model.contract_version == sb.CONTRACT_VERSION and resp.model.embedding_dim == 8


@pytest.mark.parametrize("auth,code", [
    (None, grpc.StatusCode.UNAUTHENTICATED),
    ("Bearer basura", grpc.StatusCode.UNAUTHENTICATED),
    (f"Bearer {token(iss='http://otro/realms/x')}", grpc.StatusCode.UNAUTHENTICATED),
    (f"Bearer {token(exp_in=-10)}", grpc.StatusCode.UNAUTHENTICATED),
    (f"Bearer {token(roles=('app-developer',))}", grpc.StatusCode.PERMISSION_DENIED),
])
def test_reload_exige_jwt_con_rol(env, auth, code):
    registry, _, stub, _, tmp = env
    registry.version, registry.path = "1", make_bundle(tmp / "v1")
    metadata = [("authorization", auth)] if auth else []
    with pytest.raises(grpc.RpcError) as e:
        stub.Reload(pb.ReloadRequest(), metadata=metadata)
    assert e.value.code() == code


def test_reload_cambia_version_y_es_idempotente(env):
    registry, _, stub, _, tmp = env
    md = [("authorization", f"Bearer {token()}")]
    registry.version, registry.path = "1", make_bundle(tmp / "v1")
    assert stub.Reload(pb.ReloadRequest(), metadata=md).reloaded
    assert not stub.Reload(pb.ReloadRequest(), metadata=md).reloaded  # misma versión
    registry.version, registry.path = "2", make_bundle(tmp / "v2", dim=16, seed=1)  # otra dimensión: compatible
    resp = stub.Reload(pb.ReloadRequest(), metadata=md)
    assert resp.reloaded and resp.model.version == "2" and resp.model.embedding_dim == 16


def test_reload_incompatible_mantiene_el_modelo_actual(env):
    registry, _, stub, _, tmp = env
    md = [("authorization", f"Bearer {token()}")]
    registry.version, registry.path = "1", make_bundle(tmp / "v1")
    stub.Reload(pb.ReloadRequest(), metadata=md)
    registry.version, registry.path = "2", make_bundle(tmp / "v2", contract=99)
    with pytest.raises(grpc.RpcError) as e:
        stub.Reload(pb.ReloadRequest(), metadata=md)
    assert e.value.code() == grpc.StatusCode.FAILED_PRECONDITION
    assert stub.GetModelInfo(pb.GetModelInfoRequest()).version == "1"
    assert len(stub.Recommend(pb.RecommendRequest(movie_ids=[1000], k=3)).items) == 3


def test_k_invalido(env):
    registry, _, stub, _, tmp = env
    registry.version, registry.path = "1", make_bundle(tmp / "v1")
    stub.Reload(pb.ReloadRequest(), metadata=[("authorization", f"Bearer {token()}")])
    for k in (-1, 101):
        with pytest.raises(grpc.RpcError) as e:
            stub.Recommend(pb.RecommendRequest(movie_ids=[1000], k=k))
        assert e.value.code() == grpc.StatusCode.INVALID_ARGUMENT
