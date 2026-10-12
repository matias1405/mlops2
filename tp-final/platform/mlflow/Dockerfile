FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

WORKDIR /mlflow
# Parches de seguridad del sistema operativo de la imagen base (trivy).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --system --uid 1001 --home-dir /mlflow mlflow

USER mlflow
EXPOSE 5000

# --serve-artifacts: el server hace de proxy hacia s3://mlflow-artifacts. Los clientes
# (Airflow, recommender) suben y bajan artefactos por HTTP y nunca reciben credenciales de MinIO.
# Backend store y credenciales S3 llegan por variables de entorno desde el compose.
CMD mlflow server \
    --host 0.0.0.0 \
    --port 5000 \
    --workers 2 \
    --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
    --serve-artifacts \
    --artifacts-destination "s3://mlflow-artifacts"
