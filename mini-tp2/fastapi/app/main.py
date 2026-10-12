"""API REST que sirve el modelo de rentabilidad de películas (Mini-TP1).

Carga un `model.joblib` (entrenado con `train-model/train_model.py`) al arrancar
y expone `/health` y `/v1/predict`. El contrato Pydantic coincide con las
features crudas que espera el Pipeline (FeatureEngineering se encarga de
transformarlas internamente).
"""
import json
import os
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import necesario aunque no se use directamente: joblib.load necesita poder
# resolver `model_features.FeatureEngineering` (el módulo bajo el que se
# pickleó el Pipeline en train-model/train_model.py).
from model_features import FeatureEngineering  # noqa: F401

MODEL_PATH = Path(os.environ.get("MODEL_PATH", "/app/model/model.joblib"))
MODEL_VERSION = os.environ.get("MODEL_VERSION", "1.0.0")
MODEL_NAME = os.environ.get("MODEL_NAME", "PredictionMovies")
METRICS_PATH = Path(os.environ.get("METRICS_PATH", "/app/model/metrics.json"))

app = FastAPI(title="PredictionMovies API", version=MODEL_VERSION)

allowed_origins = [
    "http://localhost:3001",
    "http://localhost:5173",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = None


class PredictionRequest(BaseModel):
    runtime: float = Field(..., gt=0, description="Duración en minutos")
    budget: float = Field(..., gt=0, description="Presupuesto en USD")
    original_language: str = Field(..., min_length=2, max_length=5)
    release_date: str = Field(..., description="Fecha ISO, ej. 2024-07-15")
    genres: list[str] = Field(..., min_length=1)
    production_companies: list[str] = Field(default_factory=list)
    production_countries: list[str] = Field(..., min_length=1)


class PredictionResponse(BaseModel):
    prediction: int
    probability: float | None = None
    model_version: str


class Metrics(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float


class ModelMetadata(BaseModel):
    name: str
    version: str
    metrics: Metrics


@app.on_event("startup")
def load_model():
    global model
    try:
        model = joblib.load(MODEL_PATH)
    except FileNotFoundError:
        model = None


@app.get("/health")
def health(response: Response):
    if model is None:
        response.status_code = 503
        return {
            "status": "waiting_for_model",
            "model_path": str(MODEL_PATH),
            "model_loaded": False,
        }

    return {
        "status": "ok",
        "model_version": MODEL_VERSION,
        "model_loaded": True,
    }


@app.get("/v1/metrics", response_model=ModelMetadata)
def get_metrics():
    """Equivalente REST de la query GraphQL `model { name version metrics {...} }`
    - mismo shape de respuesta, para comparar ambos de forma justa (Mini-TP2, punto 4)."""
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="metrics.json no encontrado")

    data = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return ModelMetadata(name=MODEL_NAME, version=MODEL_VERSION, metrics=Metrics(**data))


@app.post("/v1/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    if model is None:
        raise HTTPException(status_code=503, detail="Modelo no cargado todavía")

    df = pd.DataFrame([request.model_dump()])
    prediction = model.predict(df)[0]

    probability = None
    if hasattr(model, "predict_proba"):
        probability = float(model.predict_proba(df)[0][1])

    return PredictionResponse(
        prediction=int(prediction),
        probability=probability,
        model_version=MODEL_VERSION,
    )
