#!/bin/bash
# Crea una base y un usuario por servicio. Corre una única vez, cuando el volumen
# de datos de Postgres está vacío (docker-entrypoint-initdb.d).
#
# Cada base queda con dueño propio y sin CONNECT para PUBLIC: un servicio no puede
# conectarse a la base de otro aunque compartan la instancia.
set -euo pipefail

create_db() {
  local name="$1" password="$2"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-EOSQL
    CREATE ROLE "$name" LOGIN PASSWORD '$password';
    CREATE DATABASE "$name" OWNER "$name";
    REVOKE ALL ON DATABASE "$name" FROM PUBLIC;
EOSQL
  echo "base y usuario '$name' creados"
}

create_db airflow   "$AIRFLOW_DB_PASSWORD"
create_db mlflow    "$MLFLOW_DB_PASSWORD"
create_db keycloak  "$KEYCLOAK_DB_PASSWORD"
create_db app_dev   "$APP_DEV_DB_PASSWORD"
create_db app_prod  "$APP_PROD_DB_PASSWORD"
