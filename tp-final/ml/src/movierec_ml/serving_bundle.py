"""Contrato del artefacto de serving `movierec` (ver README, "Serving y API").

Un bundle es un directorio con:
    embeddings.npy   float32 (n, embedding_dim), filas L2-normalizadas
    movie_ids.npy    int64 (n,), mismo orden que embeddings: traduce fila <-> id de película
    manifest.json    contract_version, embedding_dim, n_movies, text_columns, git_sha, ...

`embedding_dim` es metadata: el recommender sirve cualquier dimensión. Solo un cambio de
CONTRACT_VERSION (archivos, nombres o semántica) rompe la compatibilidad. Los títulos, géneros y posters
no viajan en el bundle: el catálogo de cada ambiente sale de gold/app_catalog (ver catalog_db.sync_catalog).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

CONTRACT_VERSION = 2
SUPPORTED_CONTRACTS = {2}


class IncompatibleBundle(ValueError):
    pass


def write_bundle(path: Path, embeddings: np.ndarray, movie_ids, manifest: dict) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    np.save(path / "embeddings.npy", embeddings.astype(np.float32))
    np.save(path / "movie_ids.npy", np.asarray(movie_ids, dtype=np.int64))
    manifest = {"contract_version": CONTRACT_VERSION, "embedding_dim": int(embeddings.shape[1]),
                "n_movies": int(embeddings.shape[0]), **manifest}
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    return path


def load_bundle(path: Path, supported: set[int] = SUPPORTED_CONTRACTS) -> dict:
    """Carga y valida un bundle. Lanza IncompatibleBundle si el contrato no es soportado o está corrupto."""
    path = Path(path)
    manifest = json.loads((path / "manifest.json").read_text())
    if manifest.get("contract_version") not in supported:
        raise IncompatibleBundle(f"contract_version={manifest.get('contract_version')} no soportado {sorted(supported)}")
    emb = np.load(path / "embeddings.npy")
    ids = np.load(path / "movie_ids.npy")
    if emb.shape != (manifest["n_movies"], manifest["embedding_dim"]) or len(ids) != len(emb):
        raise IncompatibleBundle("dimensiones inconsistentes entre embeddings, ids y manifest")
    return {"manifest": manifest, "embeddings": emb, "movie_ids": ids}


def per_seed_quota(n_seeds: int, k: int, min_per_seed: int = 3) -> int:
    """Vecinos por semilla: 3 como mínimo; con pocas semillas, los necesarios para poder llenar k."""
    return max(min_per_seed, -(-k // max(n_seeds, 1)))


def recommend_per_seed(embeddings: np.ndarray, seed_rows: list[int], k: int = 12,
                       min_per_seed: int = 3) -> list[tuple[int, float, int]]:
    """Estrategia de serving (implementación de referencia, numpy).

    1. Para cada semilla, sus `per_seed_quota` vecinos más cercanos por coseno (sin otras semillas).
    2. Similitud normalizada por semilla: z = (sim - media) / desvío de las similitudes de esa semilla
       contra todo el catálogo (una semilla en una zona densa no domina a una más aislada).
    3. Se unen los candidatos (un candidato de dos semillas conserva su mejor z) y se devuelven los k
       de mayor z. Una semilla puede no aportar ninguno. Si por vecinos compartidos quedan menos de k
       candidatos únicos, la cuota por semilla se amplía de a uno hasta poder llenar k.
    Devuelve (fila, z, fila_semilla) ordenado por z descendente.
    """
    seeds = list(dict.fromkeys(seed_rows))
    quota = per_seed_quota(len(seeds), k, min_per_seed)
    sims = embeddings @ embeddings[seeds].T                 # (n, n_seeds)
    mu, sd = sims.mean(axis=0), sims.std(axis=0)
    sd[sd == 0] = 1e-9
    masked = sims.copy()
    masked[seeds, :] = -np.inf
    zscores = (sims - mu) / sd
    order = np.argsort(-masked, axis=0)                     # vecinos de cada semilla, de más a menos cercano
    available = len(embeddings) - len(seeds)
    while True:
        best: dict[int, tuple[float, int]] = {}
        for j, seed in enumerate(seeds):
            for i in order[:min(quota, available), j]:
                z = float(zscores[i, j])
                if i not in best or z > best[int(i)][0]:
                    best[int(i)] = (z, seed)
        # Si las semillas comparten vecinos quedan menos de k únicos: se amplía la cuota de a uno.
        if len(best) >= k or quota >= available:
            break
        quota += 1
    ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[:k]
    return [(i, z, seed) for i, (z, seed) in ranked]


try:
    import mlflow.pyfunc

    class MovieRecModel(mlflow.pyfunc.PythonModel):
        """Wrapper pyfunc: permite `mlflow models predict` y carga estándar desde el registry.

        Entrada: DataFrame con columnas movie_ids (lista de ids) y opcionalmente k. Usa la misma estrategia
        por semilla que el recommender-svc.
        """

        def load_context(self, context):
            self.bundle = load_bundle(Path(context.artifacts["bundle"]))
            self.index = {int(m): i for i, m in enumerate(self.bundle["movie_ids"])}

        def predict(self, context, model_input: pd.DataFrame, params=None):
            ids = self.bundle["movie_ids"]
            rows = []
            for _, row in model_input.iterrows():
                k = int(row.get("k", 12) or 12)
                seeds = [self.index[m] for m in row["movie_ids"] if m in self.index]
                recs = recommend_per_seed(self.bundle["embeddings"], seeds, k) if seeds else []
                rows.append([{"id": int(ids[i]), "score": z, "because_of": int(ids[s])} for i, z, s in recs])
            return rows
except ImportError:  # el recommender-svc no necesita mlflow.pyfunc para leer el bundle
    MovieRecModel = None

# Ejemplos cualitativos fijos del model card (si no están en el catálogo se usan las más votadas).
EXAMPLE_IDS = (862, 155, 597)  # Toy Story, The Dark Knight, Titanic


def examples(embeddings: np.ndarray, catalog: pd.DataFrame, n: int = 5) -> list[dict]:
    """Para 3 películas fijas, sus n vecinos más cercanos en el bundle (el mismo producto punto del serving)."""
    index = {int(m): i for i, m in enumerate(catalog["id"])}
    seeds = [index[m] for m in EXAMPLE_IDS if m in index]
    if len(seeds) < 3:
        extra = catalog.sort_values("vote_count", ascending=False).index if "vote_count" in catalog else catalog.index
        seeds += [int(i) for i in extra if int(i) not in seeds][:3 - len(seeds)]
    out = []
    for s in seeds:
        sims = embeddings @ embeddings[s]
        sims[s] = -np.inf
        top = np.argsort(-sims)[:n]
        out.append({"title": catalog.iloc[s]["title"],
                    "neighbors": [(catalog.iloc[i]["title"], round(float(sims[i]), 3)) for i in top]})
    return out


def model_card(cfg: dict, metrics: dict, heads: str, dataset: dict, training: pd.DataFrame, samples: list[dict]) -> str:
    langs = training["original_language"].value_counts().head(5).to_dict() if len(training) else {}
    total = len(training) or 1
    lang_txt = ", ".join(f"{lang} {100 * n / total:.0f}%" for lang, n in list(langs.items())[:5]) or "s/d"
    tabular = cfg.get("tabular", {})
    head_2 = next(c for c in cfg["targets"] if c != "genres")

    def fmt(v):
        return "n/a" if v is None else f"{v:.3f}"

    rows = "\n".join(f"| {m} | {fmt(metrics.get(m))} |" for m in ("f1_genre", "f1_company", "f1_language", "f1_mean"))
    ex = "\n".join(f"- **{e['title']}** → " + ", ".join(f"{t} ({s})" for t, s in e["neighbors"]) for e in samples)
    return f"""# Model card — movierec {cfg['name']}

## Qué hace
Recomendaciones de día 0 (cold start): el usuario elige 5 películas; el recommender toma los 3 vecinos más
cercanos de cada una (producto punto entre embeddings), los normaliza con un z-score por semilla y devuelve
los 12 mejores, cada uno con la película elegida de la que sale.

## Cómo se entrenó
- Clasificador de dos salidas (PyTorch): EmbeddingBag sobre `{', '.join(cfg['text_columns'])}` + tabular
  (numéricas `{', '.join(tabular.get('numeric', []))}`; categóricas `{', '.join(tabular.get('categorical', {}))}`)
  -> tronco de dimensión {cfg['embedding_dim']} -> cabezas `genres` y `{head_2}` (`heads={heads}`).
- Las cabezas solo sirven para entrenar: el embedding de película es la salida del tronco.
- Early stopping por val_loss. Embeddings: una pasada hacia adelante con los pesos finales, solo sobre las
  {dataset.get('app_catalog_rows')} películas de gold/app_catalog.
- Datos: gold/training ({dataset.get('rows')} películas) y gold/app_catalog ({dataset.get('app_catalog_rows')}
  películas recomendables).

## Métricas (F1 micro sobre el split test)
| Métrica | Valor |
|---|---|
{rows}

`n/a`: la cabeza no existe en esta config. En idioma (multi-clase), F1 micro = accuracy.

## Ejemplos (vecinos más cercanos)
{ex}

## Limitaciones
- Solo contenido: no usa interacciones de usuarios (por diseño, cold start).
- Sesgo por idioma del dataset: {lang_txt}. El F1 micro está dominado por las clases grandes.
- Solo se recomiendan las películas de gold/app_catalog (las más votadas).
"""
