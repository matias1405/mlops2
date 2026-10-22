# Graph Report - tp-final  (2026-10-15)

## Corpus Check
- 74 files · ~354,166 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 21 file(s) not represented in the graph (top: (none) 10, .template 6, .csv 1)

## Summary
- 632 nodes · 1031 edges · 39 communities (31 shown, 7 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 59 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6acd0280`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- test_server.py
- main.py
- App.tsx
- test_gateway.py
- movierec — recomendaciones de día 0 con una plataforma MLOps
- recommender_pb2_grpc.py
- package.json
- promote
- catalog_db.py
- clean
- serving_bundle.py
- dataops/pipeline.py
- train_and_register
- train.py
- compilerOptions
- gold_app_catalog_schema
- Tabular
- sources.py
- MovieEncoder
- test_training.py
- build_training
- data.py
- Target
- predict
- ingest_tmdb
- read_raw
- gen_secrets.py
- download_tmdb
- KeycloakSecurityManager
- bootstrap
- promote_dag
- init.sh
- 01-init.sh
- training/__init__.py
- init_roles.py
- scan_images.sh
- recommender/app/__init__.py
- movierec-ml

## God Nodes (most connected - your core abstractions)
1. `fit()` - 20 edges
2. `clean()` - 14 edges
3. `Tabular` - 14 edges
4. `train_and_register()` - 14 edges
5. `ModelStore` - 14 edges
6. `RecommenderServicer` - 13 edges
7. `Repository` - 12 edges
8. `compilerOptions` - 12 edges
9. `movierec — recomendaciones de día 0 con una plataforma MLOps` - 12 edges
10. `sync_catalog()` - 11 edges

## Surprising Connections (you probably didn't know these)
- `sync()` --calls--> `sync_catalog()`  [INFERRED]
  ml/dags/sync_catalog.py → ml/src/movierec_ml/catalog_db.py
- `reload_recommenders()` --calls--> `sync_catalog()`  [INFERRED]
  ml/dags/train_movierec.py → ml/src/movierec_ml/catalog_db.py
- `smoke_tests()` --calls--> `validate_dev()`  [INFERRED]
  ml/dags/validate_dev.py → ml/src/movierec_ml/release.py
- `encode_inputs()` --uses--> `Vocab`  [INFERRED]
  ml/src/movierec_ml/training/train.py → ml/src/movierec_ml/training/data.py
- `fit()` --uses--> `Vocab`  [INFERRED]
  ml/src/movierec_ml/training/train.py → ml/src/movierec_ml/training/data.py

## Import Cycles
- None detected.

## Communities (39 total, 7 thin omitted)

### Community 0 - "test_server.py"
Cohesion: 0.05
Nodes (45): Event, HealthServicer, Paquete del recomendador cold start: dataops, training, evaluation y…, Stubs gRPC generados desde services/proto/recommender.proto (make proto). No…, JwtValidator, PermissionDenied, Exception, Validación de JWT (Keycloak, realm platform) para el RPC Reload. (+37 more)

### Community 1 - "main.py"
Cohesion: 0.06
Nodes (38): AsyncConnectionPool, BaseModel, FastAPI, get, HTTPAuthorizationCredentials, limit, post, current_user() (+30 more)

### Community 2 - "App.tsx"
Cohesion: 0.10
Nodes (27): keycloak-js, react, Api, ApiError, createApi(), request(), ModelInfo, Movie (+19 more)

### Community 3 - "test_gateway.py"
Cohesion: 0.08
Nodes (19): AsyncClient, mock, PosterService, Posters con cache-aside: la primera vez se bajan de TMDB y se guardan en MinIO;…, auth(), client(), FakeJwks, FakeRecommender (+11 more)

### Community 4 - "movierec — recomendaciones de día 0 con una plataforma MLOps"
Cohesion: 0.05
Nodes (34): Bases operativas (PostgreSQL), Catálogo de datos, Catálogo en S3 y en la base, Data lake (MinIO, compatible con S3), Datos personales, Licencias y atribución, Credenciales de servicio (no son personas), Matriz rol × herramienta (+26 more)

### Community 5 - "recommender_pb2_grpc.py"
Cohesion: 0.07
Nodes (22): dag, DAG de entrenamiento: gold/training -> clasificador de 2 salidas (PyTorch) ->…, train_movierec(), gate_and_alias(), reload_recommenders(), train_and_register(), Missing associated documentation comment in .proto file., Missing associated documentation comment in .proto file. (+14 more)

### Community 6 - "package.json"
Cohesion: 0.06
Nodes (32): @fontsource/barlow, @fontsource/barlow-condensed, @fontsource/permanent-marker, react-dom, @types/react, @types/react-dom, typescript, vite (+24 more)

### Community 7 - "promote"
Cohesion: 0.11
Nodes (21): dag, Valida DEV antes de una release: smoke tests contra el api-gateway de DEV…, validate_dev_dag(), smoke_tests(), _model(), _now(), promote(), _qa_token() (+13 more)

### Community 8 - "catalog_db.py"
Cohesion: 0.12
Nodes (21): dag, Sincroniza el catálogo de un ambiente (app_<env>.catalog) con el modelo de su…, sync_catalog_dag(), sync(), app_dsn(), build_catalog(), build_onboarding_pool(), _isna() (+13 more)

### Community 9 - "clean"
Cohesion: 0.13
Nodes (16): _blank(), clean(), parse_list(), _plausible_year(), Series, Lectura del CSV crudo, limpieza bronze -> silver y datasets gold por uso., Action, Science Fiction' -> ['Action', 'Science Fiction']; nulo -> []., Años imposibles para una película (fechas mal cargadas, p.ej. 1800) -> nulo. (+8 more)

### Community 10 - "serving_bundle.py"
Cohesion: 0.13
Nodes (18): examples(), IncompatibleBundle, load_bundle(), model_card(), MovieRecModel, per_seed_quota(), DataFrame, ndarray (+10 more)

### Community 11 - "dataops/pipeline.py"
Cohesion: 0.19
Nodes (17): download_cached(), exists(), put_parquet(), Path, Acceso al data lake (MinIO/S3) con el usuario del servicio que corre la tarea.…, Baja un objeto a una cache local indexada por su ETag (evita re-bajar 600 MB…, s3_client(), bronze_is_empty() (+9 more)

### Community 12 - "train_and_register"
Cohesion: 0.18
Nodes (16): load_gold(), DataFrame de gold training o app_catalog., evaluate(), heads_tag(), loggable(), DataFrame, Evaluación offline: F1 micro de cada cabeza sobre el split test de…, genre,company' o 'genre,language' (tag del run y de la versión del modelo). (+8 more)

### Community 13 - "train.py"
Cohesion: 0.23
Nodes (13): build_text(), Une las columnas de texto elegidas en la config (las listas, p.ej. keywords, se…, _batches(), encode_inputs(), fit(), Inputs, _loss(), DataFrame (+5 more)

### Community 14 - "compilerOptions"
Cohesion: 0.14
Nodes (13): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noUnusedLocals, noUnusedParameters (+5 more)

### Community 15 - "gold_app_catalog_schema"
Cohesion: 0.21
Nodes (11): Check, DataFrameSchema, gold_app_catalog_schema(), gold_training_schema(), _is_list(), Contratos de datos (pandera) de cada capa del lake. - bronze: el CSV crudo…, `vote_count >= min_vote_count`., Lista (en memoria) o array de numpy (leída desde parquet). (+3 more)

### Community 16 - "Tabular"
Cohesion: 0.26
Nodes (5): _as_list(), DataFrame, ndarray, Features de entrada no textuales. numeric: log1p(budget) y año estandarizados…, Tabular

### Community 17 - "sources.py"
Cohesion: 0.20
Nodes (9): DataOps del dataset TMDB: descarga única -> bronze -> validación -> silver ->…, download_kaggle(), kaggle_metadata(), local_file(), Path, Obtención del CSV crudo de TMDB para bronze (una sola vez, ver DAG…, Versión vigente, licencia y tamaño del archivo (endpoints públicos, sin…, Baja el CSV en streaming a `dest` (sigue el redirect al storage de Kaggle) y… (+1 more)

### Community 18 - "MovieEncoder"
Cohesion: 0.27
Nodes (7): collate(), MovieEncoder, Tensor, Clasificador de dos salidas: texto (EmbeddingBag) + tabular -> tronco…, Embedding de película (salida del tronco). Es lo único que se usa en serving., Formato de EmbeddingBag: tokens concatenados + offset de inicio de cada…, test_modelo_formas()

### Community 19 - "test_training.py"
Cohesion: 0.20
Nodes (5): Split determinístico por id: la misma película cae siempre en el mismo conjunto., split_of(), test_embeddings_solo_de_app_catalog_y_bundle(), test_split_determinista_y_proporciones(), test_tabular_estandariza_y_marca_nulos()

### Community 20 - "build_training"
Cohesion: 0.28
Nodes (9): build_app_catalog(), build_training(), DataFrame, Gold training: películas con texto y etiquetas completos y `vote_count >…, Gold app_catalog: subset recomendable (⊂ training, así toda película tiene…, test_gold_app_catalog_es_subconjunto_de_training(), app_catalog(), fixture (+1 more)

### Community 21 - "data.py"
Cohesion: 0.39
Nodes (4): Preparación de datos: texto por película, tokenizer, features tabulares,…, tokenize(), Vocab, test_tokenize_y_vocab()

### Community 22 - "Target"
Cohesion: 0.29
Nodes (6): Series, Valores más frecuentes de una columna (listas o escalares), en orden de…, Una salida del clasificador. multilabel: columna lista (géneros, productoras)…, Target, top_values(), test_targets_configurables()

### Community 23 - "predict"
Cohesion: 0.29
Nodes (8): embed(), _losses(), predict(), ndarray, Pasada hacia adelante con los pesos fijos hasta el tronco; filas…, Predicción de cada cabeza: multi-label = sigmoid >= 0.5; multi-clase = argmax., Module, no_grad

### Community 24 - "ingest_tmdb"
Cohesion: 0.43
Nodes (6): ingest_tmdb(), build_gold(), build_silver(), validate_bronze(), dag, DAG de ingesta TMDB (DataOps): bronze -> validación -> silver -> gold training…

### Community 25 - "read_raw"
Cohesion: 0.29
Nodes (5): Path, Lee solo RAW_COLUMNS con pyarrow (los overview tienen saltos de línea dentro de…, read_raw(), fixture, raw_sample()

### Community 26 - "gen_secrets.py"
Cohesion: 0.43
Nodes (6): generate(), keys_of(), Path, Genera los .env a partir de sus plantillas reemplazando <generate> por secretos…, render(), render_line()

### Community 27 - "download_tmdb"
Cohesion: 0.40
Nodes (4): download_tmdb(), download_to_bronze(), dag, DAG de descarga única del dataset TMDB a bronze (DataOps), sin credenciales.…

### Community 28 - "KeycloakSecurityManager"
Cohesion: 0.50
Nodes (3): FabAirflowSecurityManagerOverride, KeycloakSecurityManager, Login de la UI de Airflow con Keycloak (realm `platform`) vía Flask-AppBuilder…

### Community 29 - "bootstrap"
Cohesion: 0.40
Nodes (3): bootstrap(), dag, Primera carga de una instalación nueva: descarga -> ingesta -> entrenamiento v1…

### Community 30 - "promote_dag"
Cohesion: 0.50
Nodes (4): promote_dag(), promote(), dag, Promoción a PROD desde la UI de Airflow (Trigger DAG w/ config). model_version…

## Knowledge Gaps
- **73 isolated node(s):** `movierec-ml`, `scan_images.sh script`, `name`, `private`, `version` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 271 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_gold()` connect `train_and_register` to `catalog_db.py`, `dataops/pipeline.py`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `sync_catalog()` connect `catalog_db.py` to `train_and_register`, `recommender_pb2_grpc.py`, `promote`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `fit()` (e.g. with `split_of()` and `Tabular`) actually correct?**
  _`fit()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Tabular` (e.g. with `encode_inputs()` and `fit()`) actually correct?**
  _`Tabular` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `ModelStore` (e.g. with `build_server()` and `initial_load()`) actually correct?**
  _`ModelStore` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `movierec-ml`, `scan_images.sh script`, `name` to the rest of the system?**
  _73 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.054987212276214836 - nodes in this community are weakly interconnected._