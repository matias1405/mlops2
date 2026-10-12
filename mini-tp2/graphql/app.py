"""API GraphQL (Strawberry + FastAPI) que expone los metadatos del modelo
de rentabilidad de películas, según la consigna de mini_tp2_actividad.ipynb:
un tipo `Model` (name, version, metrics) y una query que devuelve las
métricas de evaluación.

Lee las métricas reales de `model/metrics.json` (el mismo archivo que genera
train-model/train_model.py en el Mini-TP1) en vez de simularlas. Si no existe,
devuelve métricas en 0.0 para que el esquema siga siendo válido de punta a punta.
"""
import json
import os
from pathlib import Path
from typing import Optional

import strawberry
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

METRICS_PATH = Path(os.environ.get("METRICS_PATH", "/app/model/metrics.json"))
MODEL_NAME = os.environ.get("MODEL_NAME", "PredictionMovies")
MODEL_VERSION = int(os.environ.get("MODEL_VERSION", "1"))

DEFAULT_METRICS = {
    "accuracy": 0.0,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "roc_auc": 0.0,
}


def load_metrics() -> dict:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return DEFAULT_METRICS


@strawberry.type
class Metrics:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float


@strawberry.type
class Model:
    name: str
    version: int

    @strawberry.field
    def metrics(self) -> Metrics:
        m = load_metrics()
        return Metrics(
            accuracy=m.get("accuracy", 0.0),
            precision=m.get("precision", 0.0),
            recall=m.get("recall", 0.0),
            f1=m.get("f1", 0.0),
            roc_auc=m.get("roc_auc", 0.0),
        )


@strawberry.type
class Query:
    @strawberry.field
    def model(self, name: Optional[str] = None) -> Model:
        return Model(name=name or MODEL_NAME, version=MODEL_VERSION)


schema = strawberry.Schema(query=Query)

app = FastAPI(
    title="PredictionMovies GraphQL API",
    description="Metadatos del modelo (name, version, metrics) - Mini-TP2",
    version=str(MODEL_VERSION),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")


@app.get("/status")
async def get_status() -> dict:
    return {
        "status": "running",
        "api_type": "GraphQL",
        "metrics_found": METRICS_PATH.exists(),
    }
