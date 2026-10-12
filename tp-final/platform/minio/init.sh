#!/bin/sh
# Inicializa MinIO: buckets del data lake, lectura anónima de posters
# y un usuario con su policy por servicio (mínimo privilegio; nadie usa root).
# Es idempotente: se puede volver a correr sin romper nada.
set -eu

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

for bucket in bronze silver gold mlflow-artifacts posters; do
  mc mb --ignore-existing "local/$bucket"
done

# Buckets sin versionado: cada dataset tiene una ruta fija y re-ingestar lo sobrescribe. bronze se escribe
# una sola vez (download_tmdb nunca sobrescribe).

# Solo el bucket de posters es legible sin credenciales (lo sirve nginx en /media).
mc anonymous set download local/posters

for policy in /policies/*.json; do
  mc admin policy create local "$(basename "$policy" .json)" "$policy"
done

add_user() {
  user="$1" secret="$2" policy="$3"
  mc admin user add local "$user" "$secret"
  # attach falla si la policy ya estaba asociada (re-ejecución): se ignora.
  mc admin policy attach local "$policy" --user "$user" 2>/dev/null || true
  echo "usuario '$user' -> policy '$policy'"
}

add_user airflow      "$MINIO_AIRFLOW_SECRET"      lake-airflow
add_user mlflow       "$MINIO_MLFLOW_SECRET"       mlflow-artifacts
add_user gateway-dev  "$MINIO_GATEWAY_DEV_SECRET"  posters-writer
add_user gateway-prod "$MINIO_GATEWAY_PROD_SECRET" posters-writer

echo "MinIO inicializado"
