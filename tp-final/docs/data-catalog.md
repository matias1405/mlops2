# Catálogo de datos

Qué datos maneja movierec, dónde viven, quién es responsable de cada uno y cuánto tiempo se guardan.
El responsable de los datos es el rol `data-scientist` (ver `docs/roles.md`).

## Data lake (MinIO, compatible con S3)

Cada dataset tiene una ruta fija. Silver es la versión confiable y reutilizable del crudo, y cada consumidor tiene su propio dataset gold, con sus columnas y sus filtros.

| Dataset | Ubicación | Responsable | Esquema / contrato | Retención | Escribe | Lee |
|---|---|---|---|---|---|---|
| Dataset crudo | `bronze/tmdb/TMDB_movie_dataset_v11.csv` | data-scientist | contrato `tmdb_bronze` (pandera): columnas, tipos y rangos | indefinida: se baja una sola vez y nunca se sobrescribe | DAG `download_tmdb` | `ingest_tmdb` |
| Dataset limpio | `silver/tmdb/movies.parquet` | data-scientist | contrato `tmdb_silver`: Released, no adultas, con título y overview, ids únicos, listas parseadas (géneros, keywords, productoras); **sin filtro de votos** | se reemplaza en cada ingesta | `ingest_tmdb` | `ingest_tmdb` (gold) |
| Dataset de entrenamiento | `gold/training/movies.parquet` | data-scientist | contrato `tmdb_gold_training`: géneros, overview y keywords no vacíos, `vote_count > 10`; columnas del modelo (`id`, `title`, `overview`, `tagline`, `keywords`, `budget`, `release_year`, `original_language`, `genres`, `production_companies`, `vote_count`) | se reemplaza en cada ingesta | `ingest_tmdb` | `train_movierec` |
| Catálogo recomendable | `gold/app_catalog/movies.parquet` | data-scientist | contrato `tmdb_gold_app_catalog`: subconjunto de training con `vote_count >= 200` (umbral fijo); columnas de la UI (`id`, `title`, `poster_path`, `release_year`, `vote_average`, `vote_count`, `popularity`, `genres`) | se reemplaza en cada ingesta | `ingest_tmdb` | `train_movierec` (qué películas se embeben), `sync_catalog` (catálogo de cada ambiente) |
| Artefactos de modelos | `mlflow-artifacts/` (solo vía el proxy del server de MLflow) | ml-engineer | bundle de serving, contrato v2: embeddings, ids y manifest | indefinida | MLflow | recommenders (por HTTP), `sync_catalog` (ids del modelo) |
| Posters | `posters/w342/<movie_id>.jpg` | app-developer | JPEG, `Cache-Control: immutable` | indefinida (cache regenerable) | gateways (cache-aside), `sync_catalog` (precarga) | nginx `/media/posters/` (lectura anónima) |

Para bajar otra versión del dataset hay que vaciar `bronze/` desde la consola de MinIO y volver a correr `download_tmdb`.

## Bases operativas (PostgreSQL)

| Base | Tabla | Responsable | Contenido | Retención | Escribe | Lee |
|---|---|---|---|---|---|---|
| `app_dev` / `app_prod` | `catalog` | ml-engineer | las películas de gold/app_catalog que cubre el modelo del ambiente | se reemplaza en cada sincronización | Airflow (`sync_catalog`, `train_movierec`, `promote`) | gateway |
| `app_dev` / `app_prod` | `onboarding_pool` | ml-engineer | top 200 por rating ponderado (`m = 1000` votos), subconjunto del catálogo | se reemplaza con el catálogo | Airflow | gateway |
| `app_dev` / `app_prod` | `poster_cache` | app-developer | estado del poster (`cached` / `missing`) | indefinida | gateway, Airflow (precarga) | gateway |
| `mlflow` | (backend de MLflow) | ml-engineer | experimentos, runs, métricas, registry y aliases | indefinida | MLflow | equipo |
| `airflow` | (metadata de Airflow) | ml-engineer | DAG runs, usuarios y roles | por defecto de Airflow | Airflow | Airflow |
| `keycloak` | (Keycloak) | ml-engineer | realms, usuarios y clients | indefinida | Keycloak | Keycloak |

Cada base tiene su propio usuario, y `CONNECT` está revocado para `PUBLIC`: ningún servicio entra a la base de otro.

### Catálogo en S3 y en la base

- `gold/app_catalog` en S3 es la única fuente del catálogo: la produce la ingesta y define qué películas se embeben al entrenar.
- El modelo no lleva catálogo: solo los vectores y la lista de ids en el mismo orden, para que el recommender traduzca entre fila e id.
- La tabla `catalog` de cada ambiente es la copia de serving: `sync_catalog` la arma desde `gold/app_catalog` con las películas que cubre el modelo del ambiente, para que el gateway resuelva ids y arme el onboarding con SQL, sin leer el lake.

## Datos personales

- **Usuarios finales:** existen **solo en Keycloak** (realm `movierec`). La app no guarda nada que identifique a una persona ni registra lo que pide.
- **Datos de TMDB:** metadata pública de películas, sin datos personales.

## Licencias y atribución

- **TMDB:** datos e imágenes de [The Movie Database](https://www.themoviedb.org/). La app muestra la atribución exigida ("usa datos e imágenes de TMDB, pero no está avalada ni certificada por TMDB").
- **Dataset:** [Full TMDB Movies Dataset 2024](https://www.kaggle.com/datasets/asaniczka/tmdb-movies-dataset-2023-930k-movies) (Kaggle), licencia **ODC-By**. Solo se versiona un sample de 5.000 filas.
