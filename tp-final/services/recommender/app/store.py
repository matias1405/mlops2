"""Modelo cargado en memoria y su recarga atómica.

El bundle se descarga de MLflow por HTTP (proxy de artefactos): el servicio no tiene credenciales
del bucket. Un reload que falla (contrato incompatible, MLflow caído, bundle corrupto) no toca el
modelo que se está sirviendo.
"""
import logging
import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from movierec_ml import serving_bundle as sb

log = logging.getLogger(__name__)


@dataclass
class LoadedModel:
    version: str
    bundle: dict
    id_to_row: dict[int, int]
    loaded_at: str

    @property
    def manifest(self) -> dict:
        return self.bundle["manifest"]


def build(version: str, bundle: dict) -> LoadedModel:
    """Índice id -> fila. La búsqueda es kNN exacto por producto punto (= coseno: filas L2-normalizadas)."""
    ids = {int(m): i for i, m in enumerate(bundle["movie_ids"])}
    return LoadedModel(version, bundle, ids, datetime.now(UTC).isoformat(timespec="seconds"))


def mlflow_loader(model_name: str, alias: str) -> tuple[str, dict]:
    """Resuelve el alias en el registry y baja el bundle del modelo pyfunc."""
    import mlflow
    from mlflow import MlflowClient

    mv = MlflowClient().get_model_version_by_alias(model_name, alias)
    with tempfile.TemporaryDirectory() as tmp:
        path = mlflow.artifacts.download_artifacts(f"models:/{model_name}/{mv.version}", dst_path=tmp)
        bundle = sb.load_bundle(os.path.join(path, "artifacts", "bundle"))
    return str(mv.version), bundle


class ModelStore:
    def __init__(self, model_name: str, alias: str, loader: Callable[[str, str], tuple[str, dict]] = mlflow_loader):
        self.model_name, self.alias, self._loader = model_name, alias, loader
        self._current: LoadedModel | None = None
        self._lock = threading.Lock()  # serializa reloads; las lecturas usan la referencia actual

    @property
    def current(self) -> LoadedModel | None:
        return self._current

    def reload(self) -> tuple[bool, str]:
        """Devuelve (cambió, mensaje). Lanza sb.IncompatibleBundle u otras excepciones sin tocar el actual."""
        with self._lock:
            version, bundle = self._loader(self.model_name, self.alias)
            if self._current and self._current.version == version:
                return False, f"{self.model_name}@{self.alias} ya está en la versión {version}"
            new = build(version, bundle)
            previous = self._current.version if self._current else None
            self._current = new  # swap atómico de la referencia
            log.info("modelo %s@%s: %s -> %s", self.model_name, self.alias, previous, version)
            return True, f"{self.model_name}@{self.alias}: {previous} -> {version}"

    def recommend(self, movie_ids: list[int], k: int) -> tuple[list[tuple[int, float, int]], list[int]]:
        """(movie_id, score normalizado, movie_id de la semilla que lo aportó), ids desconocidos."""
        model = self._current
        if model is None:
            raise RuntimeError("no hay modelo cargado")
        rows = [model.id_to_row[m] for m in movie_ids if m in model.id_to_row]
        unknown = [m for m in movie_ids if m not in model.id_to_row]
        if not rows:
            return [], unknown
        ids = model.bundle["movie_ids"]
        recs = sb.recommend_per_seed(model.bundle["embeddings"], rows, k)
        return [(int(ids[r]), z, int(ids[seed])) for r, z, seed in recs], unknown


def model_info_dict(store: ModelStore) -> dict:
    m = store.current
    if m is None:
        return {"model_name": store.model_name, "alias": store.alias}
    man = m.manifest
    return {
        "model_name": store.model_name, "alias": store.alias, "version": m.version,
        "contract_version": int(man["contract_version"]), "embedding_dim": int(man["embedding_dim"]),
        "n_movies": int(man["n_movies"]), "config": str(man.get("model_config", "")),
        "loaded_at": m.loaded_at,
    }

