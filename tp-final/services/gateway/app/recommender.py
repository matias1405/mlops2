"""Cliente gRPC asíncrono del recommender-svc del mismo ambiente."""
import grpc

from movierec_ml.proto import recommender_pb2 as pb
from movierec_ml.proto import recommender_pb2_grpc as pb_grpc


class RecommenderUnavailable(Exception):
    pass


class RecommenderClient:
    def __init__(self, target: str, timeout_s: float = 5.0):
        self._channel = grpc.aio.insecure_channel(target)
        self._stub = pb_grpc.RecommenderStub(self._channel)
        self.timeout_s = timeout_s

    async def recommend(self, movie_ids: list[int], k: int) -> tuple[list[tuple[int, float]], list[int], dict]:
        try:
            resp = await self._stub.Recommend(pb.RecommendRequest(movie_ids=movie_ids, k=k), timeout=self.timeout_s)
        except grpc.aio.AioRpcError as exc:
            raise RecommenderUnavailable(f"{exc.code().name}: {exc.details()}") from exc
        return ([(r.movie_id, r.score, r.because_of) for r in resp.items], list(resp.unknown_movie_ids), _info(resp.model))

    async def model_info(self) -> dict:
        try:
            return _info(await self._stub.GetModelInfo(pb.GetModelInfoRequest(), timeout=self.timeout_s))
        except grpc.aio.AioRpcError as exc:
            raise RecommenderUnavailable(f"{exc.code().name}: {exc.details()}") from exc

    async def close(self) -> None:
        await self._channel.close()


def _info(m) -> dict:
    return {"model_name": m.model_name, "alias": m.alias, "version": m.version, "contract_version": m.contract_version,
            "embedding_dim": m.embedding_dim, "n_movies": m.n_movies, "config": m.config,
            "loaded_at": m.loaded_at}
