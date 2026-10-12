# Roles y separación de responsabilidades

Los roles viven en un solo lugar: **Keycloak**. Cada herramienta los traduce a sus propios permisos.

## Realms

| Realm | Quién | Registro | Usado por |
|---|---|---|---|
| `platform` | Equipo del proyecto | Cerrado: solo usuarios creados por el admin | Airflow, MLflow UI (oauth2-proxy), frontend DEV, service accounts |
| `movierec` | Usuarios finales | Abierto: todo usuario nuevo recibe `movierec-user` | Frontend PROD |

Que el frontend DEV use el realm `platform` hace que **dev no sea accesible al público**, además de que escucha solo en `127.0.0.1:8081`.

## Matriz rol × herramienta

`data-scientist` cubre datos y modelos: la misma persona baja los datos, arma los datasets gold y entrena. `ml-engineer` es el único que promueve modelos a PROD.

| Rol del realm `platform` | Airflow | MLflow UI | Reload de recommenders |
|---|---|---|---|
| `ml-engineer` | **Admin**: todo, incluidos `promote` (promoción y rollback) y `validate_dev` | ✅ | — |
| `data-scientist` | **DataScientist**: ve todo; dispara solo `download_tmdb`, `ingest_tmdb`, `sync_catalog` y `train_movierec` | ✅ | — |
| `app-developer` | **Viewer**: solo lectura | ❌ 403 | — |
| `model-deployer` (service account `airflow-deployer`) | — | — | ✅ `Reload` (gRPC) |
| `app-developer` (service account `qa-bot`) | — | — | ❌ `PermissionDenied` (solo hace los smoke tests de `validate_dev` contra DEV) |

Acceso a la app (api-gateway):

| Ambiente | Realm | Clients aceptados (`azp`) | Roles requeridos (alguno) |
|---|---|---|---|
| PROD | `movierec` | `movierec-web` | `movierec-user` |
| DEV | `platform` | `movierec-web-dev`, `qa-bot` | `data-scientist`, `ml-engineer`, `app-developer` |

Notas:
- **Airflow:**
  - El mapeo está en `platform/airflow/webserver_config.py` (`AUTH_ROLES_MAPPING`) y se re-sincroniza en cada login. Flask-AppBuilder agrega además el rol `Public`, que no tiene permisos.
  - `DataScientist` es un rol a medida que crea `platform/airflow/init_roles.py`: tiene los permisos de `Viewer` más `DAG Runs: can_create`.
  - El permiso de editar, y por lo tanto disparar, cada DAG lo da el propio DAG con `access_control`, y lo aplica `airflow sync-perm --include-dags`.
  - `ds_user` dispara `ingest_tmdb` y `train_movierec` (200), pero recibe 403 en `promote` y `validate_dev`.
- **MLflow UI:** oauth2-proxy (`OAUTH2_PROXY_ALLOWED_ROLES`) deja pasar solo a `ml-engineer` y `data-scientist`.
- **Acceso M2M a MLflow:** Airflow y los recommenders van por la red interna `movierec_ml_platform` sin pasar por el proxy. MLflow no publica puertos.

## Credenciales de servicio (no son personas)

| Recurso | Usuario | Alcance |
|---|---|---|
| MinIO | `airflow` | lectura/escritura en `bronze`, `silver` y `gold`; escritura en `posters` (warm-up) |
| MinIO | `mlflow` | lectura/escritura en `mlflow-artifacts`. Es el único con acceso a ese bucket |
| MinIO | `gateway-dev`, `gateway-prod` | lectura/escritura en `posters` |
| Postgres | uno por base (`airflow`, `mlflow`, `keycloak`, `app_dev`, `app_prod`) | solo su propia base; `CONNECT` revocado a `PUBLIC` |
| Postgres | Airflow usa `app_dev` y `app_prod` | para sincronizar `catalog` y `onboarding_pool` antes de cada `Reload` |

## Usuarios demo

La contraseña de cada usuario demo es su nombre de usuario (plataforma de demo, solo local).

| Usuario | Realm | Rol |
|---|---|---|
| `mle_user` | platform | ml-engineer |
| `ds_user` | platform | data-scientist |
| `dev_user` | platform | app-developer |
| `client_user` | movierec | movierec-user |

## Trabajo individual

El TP lo hace una sola persona, que cubre los tres roles de equipo. Los roles igual se mantienen separados en la plataforma, y la demo los muestra con un usuario por rol. Así queda claro qué puede hacer cada responsabilidad y la plataforma está lista para un equipo real.

| Rol | Usuario demo | Responsabilidades |
|---|---|---|
| `ml-engineer` | `mle_user` | plataforma, registry de modelos, promoción a PROD y rollback (`validate_dev`, `promote`) |
| `data-scientist` | `ds_user` | descarga e ingesta, contratos de datos, datasets gold, modelos v1–v4, experimentos, model card |
| `app-developer` | `dev_user` | recommender-svc, api-gateway, frontend |

Para sumar a una persona: crear su usuario en Keycloak (realm `platform`) y asignarle el rol. Airflow y MLflow lo toman en su primer login.

**Aplicar cambios de realm:** los realms se importan solo si no existen. Para que Keycloak tome cambios de `platform/keycloak/realms/*.json` hay que borrar el realm desde la consola de admin y reiniciar Keycloak, o hacer una instalación limpia (`make clean-platform`). En Airflow, los usuarios viejos quedan en su base hasta que se borren (`airflow users delete`).
