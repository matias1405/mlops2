# Seguridad

Controles de la plataforma y riesgos aceptados.

```bash
make scan               # vulnerabilidades (trivy) de las imágenes propias
make test-ml            # tests de movierec_ml (los de recommender, gateway y web corren en el build de sus imágenes)
```

## Controles

| Área | Control | Dónde |
|---|---|---|
| **Exposición de red** | Solo web-prod (`:80`) y Keycloak (`:8180`) escuchan en `0.0.0.0`. DEV, Airflow, MLflow y la consola de MinIO solo en `127.0.0.1`. La API de MinIO, Postgres, MLflow y los servicios internos no publican puertos | `compose.*.yml` |
| **Segmentación** | Redes por dominio: `ml_platform`, `shared`, `media` y `app` por ambiente. web solo llega al gateway y a MinIO; el gateway, a su base, MinIO y Keycloak, pero no a MLflow ni a Airflow | `compose.*.yml` |
| **Autenticación** | OIDC con Keycloak: authorization code + PKCE en el navegador y client credentials para M2M. Issuer único y JWT validados contra JWKS (firma, `iss`, `exp`, `azp`) | `platform/keycloak/realms`, `services/*/app/auth.py` |
| **Autorización** | Roles por ambiente (PROD `movierec-user`; DEV solo equipo). `Reload` gRPC exige `model-deployer`. En Airflow cada rol dispara solo sus DAGs; `promote` y `validate_dev` solo ml-engineer | `docs/roles.md` |
| **Mínimo privilegio en datos** | Un usuario de Postgres por base (`CONNECT` revocado a `PUBLIC`). Un usuario de MinIO por servicio con su policy. Solo el server de MLflow tiene acceso a `mlflow-artifacts` | `platform/postgres`, `platform/minio` |
| **Secretos** | Los secretos entre servicios (bases, clients de Keycloak, usuarios de MinIO por servicio, claves de Airflow) los genera al azar `make secrets` en `*.env` (permisos 600, ignorados por git y excluidos del contexto de build por `.dockerignore`). Los realms de Keycloak no llevan secretos de servicio. En el compose, las passwords no van en los comandos. La descarga del dataset no usa credenciales (API pública de Kaggle) | `scripts/gen_secrets.py`, `.gitignore`, `.dockerignore` |
| **Contenedores** | Imágenes propias sin root (uid 10001, nginx 101, MLflow 1001; MinIO corre como 1001). recommender, gateway y web corren con root filesystem de solo lectura, `cap_drop: ALL`, `no-new-privileges` y tmpfs solo donde escriben. MinIO, MLflow, oauth2-proxy y Keycloak, con `cap_drop: ALL` y `no-new-privileges` | `compose.*.yml` |
| **Cadena de suministro** | Imágenes base pineadas por digest y dependencias Python y npm con versión fija (`package-lock.json`). Parches de seguridad del sistema operativo en cada build. Tests dentro del build: sin tests en verde no hay imagen. Escaneo con trivy en local y en CI | Dockerfiles, `make scan`, `.github/workflows/tp-final.yml` |
| **Aplicación web** | CSP restrictiva (`script-src 'self'`; `connect-src` limitado a la app y Keycloak; sin frames), `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`. `/media` solo hace GET/HEAD sobre el bucket de posters | `services/web/nginx` |
| **API** | Validación de entrada con Pydantic (exactamente 5 películas; `k` acotado), rate limit en memoria por token (60 recomendaciones por minuto) y errores sin detalles internos | `services/gateway` |
| **Datos personales** | Minimización de datos: los usuarios finales existen solo en Keycloak. La app no guarda nada que identifique a una persona ni registra lo que pide | `docs/data-catalog.md` |

## Política de vulnerabilidades (`make scan`)

- **Imágenes de la app** (recommender, gateway, web), que reciben tráfico y web es pública: **cero CRITICAL con fix disponible**, si no el escaneo falla. Las excepciones se justifican una por una en `.trivyignore`.
- **Imágenes de plataforma** (Airflow, MLflow), sin puertos públicos y con las UIs detrás de Keycloak en `127.0.0.1`: se reportan, y sus riesgos aceptados están abajo.
- Se cuentan solo las vulnerabilidades con fix disponible (`--ignore-unfixed`): las demás no son accionables desde el proyecto.

### Último escaneo (`make scan`)

| Imagen | CRITICAL | HIGH |
|---|---|---|
| movierec/recommender | **0** | 1 (pyarrow) |
| movierec/gateway | **0** | 0 |
| movierec/web | **0** | 0 |
| movierec/airflow:2.10.4 | 5 | 34 |
| movierec/mlflow:2.19.0 | 6 | 14 |

Los parches del sistema operativo (`apt-get upgrade` / `apk upgrade` en cada build) y `authlib` 1.6.9 dejan la app sin CRITICAL. Las que quedan en la plataforma son de Airflow 2.10 y MLflow 2.19 (ver abajo). El detalle por vulnerabilidad queda en `reports/security/*.json`.

## Riesgos aceptados

| Riesgo | Por qué se acepta | Mitigación |
|---|---|---|
| **Airflow 2.10.4 (EOL) y sus dependencias** (CVEs en `apache-airflow`, `h11`, `anyio`, el binario Go embebido) | Migrar a Airflow 3.x cambia la API de DAGs, el auth manager y el login con Keycloak: es trabajo de varios días fuera del alcance del TP | UI solo en `127.0.0.1` con login Keycloak; sin acceso desde el navegador público; red interna. Se cierra migrando a Airflow 3.x |
| **MLflow 2.19 (server)** con CVEs corregidas en 2.22 y 3.x | Saltar a 3.x cambia el registry y el cliente; además los clientes usan `mlflow-skinny` 2.19 | Sin puertos publicados: la UI va por oauth2-proxy con roles de Keycloak y la API solo por la red interna. Se cierra actualizando server y clientes juntos a 3.x |
| **torch 2.5.1** (CVE de `torch.load`) | El venv solo carga modelos que genera el propio pipeline, nunca archivos de terceros | El serving no usa torch (recommender sin PyTorch) |
| **pyarrow 18.1** (HIGH) | Lectura de parquet generado por el propio pipeline | Sin entradas de terceros |
| **Postgres arranca como root** | Su entrypoint inicializa el volumen y baja a `postgres` (todos sus procesos corren como `postgres`) | Sin puerto publicado; red interna |
| **Contraseñas de demo** (usuarios demo, admin de Keycloak y root de MinIO iguales a su nombre de usuario) | Plataforma de demo para uso local: las credenciales tienen que ser fáciles de recordar en la presentación | La consola de MinIO, Airflow, MLflow y DEV solo escuchan en `127.0.0.1`. Keycloak escucha en `0.0.0.0:8180` (lo usan los usuarios finales de PROD), así que su consola de admin queda accesible desde la red local: en una red compartida hay que cambiar la contraseña de `kc-admin`. Para un uso real se pone `<generate>` en `platform.env.template` y se cambian las del realm |
| **HTTP sin TLS** | Plataforma local (`localhost`): Keycloak y los navegadores tratan `localhost` como contexto seguro | En un despliegue real (AWS): TLS en el borde (ALB / ACM) y `KC_HOSTNAME` https |
| **gRPC sin TLS** | Tráfico solo dentro de la red de Docker del ambiente o de la plataforma | `Reload` igual exige JWT |
| **Fork pgsty/minio** | MinIO dejó de publicar imágenes community | Pineado por digest, mismo binario AGPL; el acceso es por API S3, intercambiable |
