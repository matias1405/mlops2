# Build context: tp-final/ (para copiar el paquete compartido movierec_ml: contrato del bundle + stubs gRPC)
FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS base

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/srv
# Parches de seguridad del sistema operativo de la imagen base (trivy).
RUN apt-get update && apt-get -y upgrade && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY services/recommender/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --system --uid 10001 --home-dir /srv recommender

# Solo lo necesario del paquete compartido (sin training ni dataops).
COPY ml/src/movierec_ml/__init__.py ml/src/movierec_ml/serving_bundle.py movierec_ml/
COPY ml/src/movierec_ml/proto movierec_ml/proto
COPY services/recommender/app app

# Tests dentro del build: si falla alguno no hay imagen. La etapa no se publica.
FROM base AS test
RUN pip install --no-cache-dir pytest==9.1.1
COPY services/recommender/tests tests
USER recommender
RUN python -m pytest -q -p no:cacheprovider tests && touch /tmp/tests-passed

# Imagen final: la base sin pytest ni tests. El COPY --from=test obliga a construir (y pasar) la etapa test.
FROM base AS runtime
COPY --from=test /tmp/tests-passed /tmp/tests-passed
USER recommender
EXPOSE 50051
HEALTHCHECK --interval=15s --timeout=5s --start-period=10m --start-interval=5s --retries=5 \
  CMD python -c "import grpc,sys; from grpc_health.v1 import health_pb2 as h, health_pb2_grpc as g; \
r=g.HealthStub(grpc.insecure_channel('localhost:50051')).Check(h.HealthCheckRequest(service=''), timeout=3); \
sys.exit(0 if r.status==h.HealthCheckResponse.SERVING else 1)"
CMD ["python", "-m", "app.server"]
