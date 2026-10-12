"""DataOps del dataset TMDB: descarga única -> bronze -> validación -> silver -> gold (training, app_catalog).

Los módulos no importan Airflow: los DAGs los llaman desde tareas comunes o desde el venv
de entrenamiento (`@task.external_python`), y los tests los usan directamente.
"""

DATASET_FILE = "TMDB_movie_dataset_v11.csv"
KAGGLE_DATASET = "asaniczka/tmdb-movies-dataset-2023-930k-movies"
