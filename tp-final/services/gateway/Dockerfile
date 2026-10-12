# Build context: tp-final/ (copia del paquete compartido: DDL de la base del ambiente + stubs gRPC)
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv
# Parches de seguridad del sistema operativo de la imagen base (trivy).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY services/gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --system --uid 10001 --home-dir /srv gateway

COPY ml/src/movierec_ml/__init__.py ml/src/movierec_ml/catalog_db.py movierec_ml/
COPY ml/src/movierec_ml/proto movierec_ml/proto
COPY services/gateway/app app

# Tests dentro del build: si falla alguno no hay imagen. La etapa no se publica.
FROM base AS test
RUN pip install --no-cache-dir pytest==9.1.1 respx==0.23.1
COPY services/gateway/tests tests
USER gateway
RUN python -m pytest -q -p no:cacheprovider tests && touch /tmp/tests-passed

# Imagen final: la base sin pytest ni tests. El COPY --from=test obliga a construir (y pasar) la etapa test.
FROM base AS runtime
COPY --from=test /tmp/tests-passed /tmp/tests-passed
USER gateway
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/api/health', timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
