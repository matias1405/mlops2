# Build context = mini-tp1/ (no fastapi/), así puede copiar el modelo entrenado
# desde ../train-model. Ver docker-compose.yml: build.context: . , dockerfile: fastapi/Dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY fastapi/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Mismo módulo (nombre y contenido) que usó train-model/train_model.py al
# entrenar - necesario para que joblib.load() pueda deserializar el Pipeline.
COPY fastapi/model_features.py ./model_features.py
COPY fastapi/app/ ./app/

# Modelo entrenado: correr train-model/train_model.py ANTES de construir esta
# imagen (genera train-model/model.joblib).
COPY train-model/model.joblib ./model/model.joblib

ENV MODEL_PATH=/app/model/model.joblib
ENV MODEL_VERSION=1.0.0

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
