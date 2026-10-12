"""Obtención del CSV crudo de TMDB para bronze (una sola vez, ver DAG download_tmdb).

    kaggle  descarga anónima por la API pública de Kaggle, fijada a la versión vigente del dataset
    local   copia de data/raw/ (dataset completo bajado a mano; sin internet)
    sample  sample versionado en data/sample/ (5.000 películas; CI y demo)

El dataset de Kaggle se actualiza todos los días: fijar la versión al bajarlo hace reproducible todo
lo que sigue. No se usan credenciales.
"""
import os
from pathlib import Path

from . import DATASET_FILE, KAGGLE_DATASET

DATA_DIR = Path(os.environ.get("MOVIEREC_DATA_DIR", "/opt/airflow/data"))
LOCAL_FILE = DATA_DIR / "raw" / DATASET_FILE
SAMPLE_FILE = DATA_DIR / "sample" / "tmdb_sample.csv"
KAGGLE_API = "https://www.kaggle.com/api/v1"
SOURCES = ("kaggle", "local", "sample")


def kaggle_metadata() -> dict:
    """Versión vigente, licencia y tamaño del archivo (endpoints públicos, sin autenticación)."""
    import requests

    view = requests.get(f"{KAGGLE_API}/datasets/view/{KAGGLE_DATASET}", timeout=30)
    view.raise_for_status()
    files = requests.get(f"{KAGGLE_API}/datasets/list/{KAGGLE_DATASET}", timeout=30)
    files.raise_for_status()
    info = view.json()
    file = next(f for f in files.json()["datasetFiles"] if f["name"] == DATASET_FILE)
    version = int(info["currentVersionNumber"])
    return {
        "source": "kaggle", "dataset": KAGGLE_DATASET, "version": version, "license": info.get("licenseName"),
        "last_updated": info.get("lastUpdated"), "size_bytes": int(file["totalBytes"]),
        "url": f"{KAGGLE_API}/datasets/download/{KAGGLE_DATASET}/{DATASET_FILE}?datasetVersionNumber={version}",
    }


def download_kaggle(meta: dict, dest: Path) -> Path:
    """Baja el CSV en streaming a `dest` (sigue el redirect al storage de Kaggle) y verifica el tamaño."""
    import requests

    tmp = dest.with_suffix(".part")
    with requests.get(meta["url"], stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                fh.write(chunk)
    size = tmp.stat().st_size
    if size != meta["size_bytes"]:
        tmp.unlink()
        raise RuntimeError(f"descarga incompleta: {size} bytes, Kaggle informa {meta['size_bytes']}")
    tmp.rename(dest)
    return dest


def local_file(source: str) -> tuple[dict, Path]:
    """Metadatos y ruta del CSV para las fuentes sin internet."""
    if source == "local":
        if not LOCAL_FILE.exists():
            raise FileNotFoundError(f"No existe {LOCAL_FILE}; copiá el dataset a data/raw/ o usá source=sample")
        path = LOCAL_FILE
    elif source == "sample":
        path = SAMPLE_FILE
    else:
        raise ValueError(f"source desconocido: {source!r} ({' | '.join(SOURCES)})")
    return {"source": source, "dataset": KAGGLE_DATASET, "version": source, "license": "ODC-By",
            "size_bytes": path.stat().st_size, "url": f"file://{path}"}, path
