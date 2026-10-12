# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "pandas",
#     "numpy",
#     "scikit-learn",
#     "joblib",
# ]
# ///
"""Entrena el modelo v1 de rentabilidad de películas y lo guarda con joblib.

Réplica autocontenida del pipeline v1 de `trabajo-final-mlops1/prediction_movies_ml`
(preprocessing.validate/clean/split + training.FeatureEngineering + RandomForestClassifier),
sin depender de ese repo ni de Airflow/MLflow/MinIO. Pensado para generar rápido el
.joblib que sirve el Mini-TP1 con FastAPI.

Uso:
    uv run train_model.py --data-path /ruta/al/TMDB_movie_dataset_v11.csv
    uv run train_model.py  # usa ./dataset/TMDB_movie_dataset_v11.csv por defecto

Salida:
    model.joblib   - el Pipeline entrenado (FeatureEngineering + VarianceThreshold + RandomForest)
    metrics.json   - accuracy/precision/recall/f1/roc_auc sobre el hold-out set
"""
import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import joblib

from model_features import FeatureEngineering

REQUIRED_COLUMNS = [
    "id",
    "adult",
    "runtime",
    "budget",
    "revenue",
    "release_date",
    "original_language",
    "genres",
    "production_countries",
    "production_companies",
]


# ---------------------------------------------------------------------------
# Preprocessing (portado de ml/v1/preprocessing/__init__.py)
# ---------------------------------------------------------------------------

def validate(df: pd.DataFrame) -> bool:
    for col in REQUIRED_COLUMNS:
        if col not in df.columns:
            raise ValueError(f"Falta la columna requerida: {col}")
    if df.empty:
        raise ValueError("El dataset está vacío")
    return True


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop_duplicates(subset="id")
    df = df[df["adult"] == False]  # noqa: E712 (misma condición que el original)
    df = df[df["runtime"] > 0]
    df = df[df["budget"] > 0]
    df = df[df["revenue"] > 0]
    df = df[df["release_date"].notna()]
    return df


def split(df: pd.DataFrame):
    df = df.copy()
    df["profitable"] = (df["revenue"] >= df["budget"]).astype(int)
    X = df.drop(columns=["profitable", "revenue", "id", "adult", "popularity", "vote_average", "vote_count"])
    y = df["profitable"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=14, stratify=y
    )
    return X_train, X_test, y_train, y_test


# ---------------------------------------------------------------------------
# Training (portado de ml/v1/training/__init__.py; FeatureEngineering vive en
# model_features.py, ver el docstring de ese módulo)
# ---------------------------------------------------------------------------

def train(x_train, y_train) -> Pipeline:
    model = Pipeline([
        ("features", FeatureEngineering()),
        ("variance_filter", VarianceThreshold(threshold=0.005)),
        ("clf", RandomForestClassifier(class_weight="balanced", random_state=14)),
    ])
    model.fit(x_train, y_train)
    return model


def evaluate(model, x_test, y_test) -> dict:
    y_pred = model.predict(x_test)
    y_pred_proba = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
        "roc_auc": roc_auc_score(y_test, y_pred_proba),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-path",
        type=Path,
        default=here / "dataset" / "TMDB_movie_dataset_v11.csv",
        help="CSV del TMDB movie dataset (default: ./dataset/TMDB_movie_dataset_v11.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=here / "model.joblib",
        help="Path de salida para el modelo entrenado (default: ./model.joblib)",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=here / "metrics.json",
        help="Path de salida para las métricas de evaluación (default: ./metrics.json)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.data_path.exists():
        raise FileNotFoundError(
            f"No se encontró el dataset en {args.data_path}. "
            "Copiá TMDB_movie_dataset_v11.csv ahí o pasá --data-path /otra/ruta."
        )

    print(f"Cargando dataset desde {args.data_path}...")
    df = pd.read_csv(args.data_path)

    print("Validando...")
    validate(df)

    print("Limpiando...")
    df = clean(df)

    print("Separando train/test...")
    X_train, X_test, y_train, y_test = split(df)

    print(f"Entrenando modelo ({len(X_train)} filas de train)...")
    model = train(X_train, y_train)

    print(f"Evaluando ({len(X_test)} filas de test)...")
    metrics = evaluate(model, X_test, y_test)
    for name, value in metrics.items():
        print(f"  {name}: {value:.4f}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.output)
    print(f"Modelo guardado en {args.output}")

    args.metrics_output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Métricas guardadas en {args.metrics_output}")


if __name__ == "__main__":
    main()
