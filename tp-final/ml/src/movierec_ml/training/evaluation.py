"""Evaluación offline: F1 micro de cada cabeza sobre el split test de gold/training.

    f1_genre     multi-label, umbral 0.5 sobre las sigmoids          (las cuatro configs)
    f1_company   multi-label sobre las productoras top 100            (v1 / v2)
    f1_language  multi-clase (argmax); con F1 micro equivale a accuracy (v3 / v4)
    f1_mean      promedio de las dos cabezas de la config

La métrica que no aplica a una config es None: MLflow no acepta nulos, así que se omite al loguear y
el JSON completo (con null explícito) va como artefacto evaluation/metrics.json.
Las clases grandes dominan el F1 micro (inglés es ~2/3 de las películas): es una decisión consciente.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from .data import METRIC_NAMES
from .train import TrainResult, predict

ALL_METRICS = ["f1_genre", "f1_company", "f1_language"]


def evaluate(result: TrainResult, training: pd.DataFrame, cfg: dict) -> dict:
    test = training[(result.splits == "test").to_numpy()]
    preds = predict(result.model, result.inputs(test, cfg), result.targets)
    metrics: dict[str, float | None] = dict.fromkeys(ALL_METRICS)
    for t in result.targets:
        y = t.encode(test)
        metrics[t.metric] = float(f1_score(y, preds[t.column], average="micro", zero_division=0))
    present = [v for v in metrics.values() if v is not None]
    metrics["f1_mean"] = float(np.mean(present)) if present else None
    return metrics


def heads_tag(result: TrainResult) -> str:
    """'genre,company' o 'genre,language' (tag del run y de la versión del modelo)."""
    return ",".join(METRIC_NAMES[t.column].removeprefix("f1_") for t in result.targets)


def loggable(metrics: dict) -> dict[str, float]:
    return {k: v for k, v in metrics.items() if v is not None}
