FROM apache/airflow:slim-2.10.4-python3.12@sha256:696ce48a24c05033f597b8df7a41cad82cdf2d6576809022a3d0734eb8d1f3b9

# Dependencias de Airflow (providers + cliente MLflow para aliases/promoción).
# Se fija apache-airflow en la misma versión para que pip no lo actualice.
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==2.10.4" -r /requirements.txt

# Venv separado para el entrenamiento (PyTorch CPU). Lo usan las tareas
# ExternalPythonOperator, así torch y sus dependencias no se mezclan con las de Airflow.
USER root
RUN mkdir -p /opt/venvs && chown airflow:0 /opt/venvs
USER airflow
COPY trainer-requirements.txt /trainer-requirements.txt
RUN python -m venv /opt/venvs/trainer \
    && /opt/venvs/trainer/bin/pip install --no-cache-dir \
       --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 \
    && /opt/venvs/trainer/bin/pip install --no-cache-dir -r /trainer-requirements.txt

# Login con Keycloak: FAB OAuth necesita authlib. Capa aparte al final para no
# invalidar la capa cacheada del venv de torch.
USER airflow
RUN pip install --no-cache-dir "apache-airflow==2.10.4" "authlib==1.6.9"

# DataOps: contratos de datos con pandera y tests del paquete movierec_ml en el venv.
# Capa aparte para reutilizar la cache de torch.
COPY trainer-extra-requirements.txt /trainer-extra-requirements.txt
RUN /opt/venvs/trainer/bin/pip install --no-cache-dir -r /trainer-extra-requirements.txt

# Parches de seguridad del sistema operativo (trivy). Última capa: no invalida la de torch.
# msodbcsql18 (driver de SQL Server de la imagen base, no se usa) exige aceptar una EULA: se retiene.
USER root
RUN apt-mark hold msodbcsql18 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get -y upgrade \
    && rm -rf /var/lib/apt/lists/*
USER airflow
