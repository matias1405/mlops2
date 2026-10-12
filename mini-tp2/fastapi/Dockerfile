# Build context = fastapi/. El modelo (model.joblib + metrics.json) NO se
# copia acá - se monta como volumen en runtime (ver docker-compose.yml), así
# reentrenar/actualizar métricas no requiere reconstruir la imagen.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Mismo módulo (nombre y contenido) que se usó al entrenar model/model.joblib
# - necesario para que joblib.load() pueda deserializar el Pipeline.
COPY model_features.py ./model_features.py
COPY app/ ./app/

ENV MODEL_PATH=/app/model/model.joblib
ENV METRICS_PATH=/app/model/metrics.json
ENV MODEL_VERSION=1.0.0
ENV MODEL_NAME=PredictionMovies

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
