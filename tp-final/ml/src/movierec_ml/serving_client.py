"""Cliente del recommender-svc para Airflow: Reload autenticado con la service account airflow-deployer."""
import os

GRPC_PORT = 50051


def deployer_token() -> str:
    """Token client_credentials del realm platform (rol model-deployer). El iss es la URL pública."""
    import time

    import requests

    url = f"{os.environ['KEYCLOAK_INTERNAL_URL']}/realms/platform/protocol/openid-connect/token"
    data = {"grant_type": "client_credentials", "client_id": "airflow-deployer",
            "client_secret": os.environ["KC_AIRFLOW_DEPLOYER_SECRET"]}
    for attempt in range(3):  # Keycloak puede tardar en responder si el host está cargado
        try:
            resp = requests.post(url, timeout=60, data=data)
            resp.raise_for_status()
            return resp.json()["access_token"]
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            time.sleep(10)


def reload_recommender(env: str, timeout_s: int = 120) -> dict:
    """Pide al recommender del ambiente que recargue su alias. Devuelve el estado sin lanzar si el
    servicio no está levantado (el recommender igual carga el alias vigente cuando arranca)."""
    import grpc

    from .proto import recommender_pb2 as pb
    from .proto import recommender_pb2_grpc as pb_grpc

    target = f"recommender-{env}:{GRPC_PORT}"
    with grpc.insecure_channel(target) as channel:
        stub = pb_grpc.RecommenderStub(channel)
        try:
            resp = stub.Reload(pb.ReloadRequest(), metadata=[("authorization", f"Bearer {deployer_token()}")],
                               timeout=timeout_s)
        except grpc.RpcError as exc:
            if exc.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED) and "no se pudo cargar" not in (exc.details() or ""):
                return {"target": target, "status": "unreachable", "detail": exc.details()}
            raise RuntimeError(f"Reload en {target} falló: {exc.code().name}: {exc.details()}") from exc
    return {"target": target, "status": "reloaded" if resp.reloaded else "unchanged",
            "version": resp.model.version, "message": resp.message}
