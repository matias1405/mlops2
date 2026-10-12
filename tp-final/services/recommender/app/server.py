"""Servidor gRPC: Recommender + grpc.health.v1 + reflexión (para grpcurl)."""
import logging
import signal
import threading
from concurrent import futures

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

from movierec_ml import serving_bundle as sb
from movierec_ml.proto import recommender_pb2 as pb
from movierec_ml.proto import recommender_pb2_grpc as pb_grpc

from .auth import JwtValidator, PermissionDenied, Unauthenticated
from .config import Settings
from .store import ModelStore, model_info_dict

log = logging.getLogger("recommender")
SERVICE = pb.DESCRIPTOR.services_by_name["Recommender"].full_name


class RecommenderServicer(pb_grpc.RecommenderServicer):
    def __init__(self, store: ModelStore, validator: JwtValidator, health_servicer: health.HealthServicer,
                 max_k: int = 100):
        self.store, self.validator, self.health, self.max_k = store, validator, health_servicer, max_k

    def _info(self) -> pb.ModelInfo:
        return pb.ModelInfo(**model_info_dict(self.store))

    def _set_serving(self) -> None:
        status = health_pb2.HealthCheckResponse.SERVING if self.store.current else health_pb2.HealthCheckResponse.NOT_SERVING
        for name in ("", SERVICE):
            self.health.set(name, status)

    def Recommend(self, request, context):
        if self.store.current is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "modelo todavía no cargado")
        k = request.k or 10
        if not 1 <= k <= self.max_k:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"k debe estar entre 1 y {self.max_k}")
        if not request.movie_ids:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "movie_ids vacío")
        items, unknown = self.store.recommend(list(request.movie_ids), k)
        return pb.RecommendResponse(items=[pb.Recommendation(movie_id=m, score=s, because_of=b) for m, s, b in items],
                                    unknown_movie_ids=unknown, model=self._info())

    def GetModelInfo(self, request, context):
        return self._info()

    def Reload(self, request, context):
        auth = dict(context.invocation_metadata()).get("authorization")
        try:
            claims = self.validator.validate(auth)
        except Unauthenticated as exc:
            context.abort(grpc.StatusCode.UNAUTHENTICATED, str(exc))
        except PermissionDenied as exc:
            context.abort(grpc.StatusCode.PERMISSION_DENIED, str(exc))
        who = claims.get("azp") or claims.get("preferred_username")
        try:
            changed, msg = self.store.reload()
        except sb.IncompatibleBundle as exc:
            log.warning("reload rechazado (pedido por %s): %s", who, exc)
            context.abort(grpc.StatusCode.FAILED_PRECONDITION, f"bundle incompatible, se mantiene el modelo actual: {exc}")
        except Exception as exc:  # MLflow caído, alias inexistente, etc.
            log.exception("reload falló (pedido por %s)", who)
            context.abort(grpc.StatusCode.UNAVAILABLE, f"no se pudo cargar el modelo, se mantiene el actual: {exc}")
        self._set_serving()
        log.info("reload pedido por %s: %s", who, msg)
        return pb.ReloadResponse(reloaded=changed, model=self._info(), message=msg)


def build_server(settings: Settings, store: ModelStore, validator: JwtValidator, port: int | None = None):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    health_servicer = health.HealthServicer()
    servicer = RecommenderServicer(store, validator, health_servicer, settings.max_k)
    pb_grpc.add_RecommenderServicer_to_server(servicer, server)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    reflection.enable_server_reflection((SERVICE, health.SERVICE_NAME, reflection.SERVICE_NAME), server)
    bound = server.add_insecure_port(f"[::]:{settings.grpc_port if port is None else port}")
    servicer._set_serving()
    return server, servicer, bound


def initial_load(store: ModelStore, servicer: RecommenderServicer, retry_s: int, stop: threading.Event) -> None:
    """Carga el modelo al arrancar; si todavía no existe el alias, reintenta sin bloquear el servidor."""
    while not stop.is_set():
        try:
            log.info(store.reload()[1])
            servicer._set_serving()
            return
        except Exception as exc:
            log.warning("modelo no disponible todavía (%s); reintento en %ss", exc, retry_s)
            stop.wait(retry_s)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings()
    store = ModelStore(settings.model_name, settings.model_alias)
    validator = JwtValidator(settings.jwt_issuer, settings.jwks_url, settings.reload_role)
    server, servicer, port = build_server(settings, store, validator)
    server.start()
    log.info("recommender-svc escuchando en :%s (modelo %s@%s)", port, settings.model_name, settings.model_alias)
    stop = threading.Event()
    threading.Thread(target=initial_load, args=(store, servicer, settings.initial_load_retry_s, stop), daemon=True).start()

    def shutdown(*_):
        stop.set()
        server.stop(grace=5)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.wait_for_termination()


if __name__ == "__main__":
    main()
