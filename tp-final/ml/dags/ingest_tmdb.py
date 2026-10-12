"""DAG de ingesta TMDB (DataOps): bronze -> validación -> silver -> gold training + gold app_catalog.

No adquiere datos: lee el CSV que dejó download_tmdb en bronze; silver y gold se sobrescriben.
Umbrales fijos (dataops/pipeline.py): gold training con vote_count > 10 y gold app_catalog con vote_count >= 200.
Las tareas corren en el venv del trainer (pandas, pyarrow, pandera), aislado de Airflow.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(
    dag_id="ingest_tmdb",
    description="bronze -> silver -> gold (training, app_catalog) con validación de contratos",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    # Separación de roles: además de Admin, solo DataScientist puede disparar este DAG.
    access_control={"DataScientist": {"can_read", "can_edit"}},
    tags=["dataops"],
)
def ingest_tmdb():
    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def validate_bronze() -> dict:
        from movierec_ml.dataops.pipeline import validate_bronze

        return validate_bronze()

    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def build_silver(bronze_check: dict) -> dict:
        from movierec_ml.dataops.pipeline import build_silver

        print(f"bronze validado: {bronze_check}")
        return build_silver()

    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def build_gold(silver: dict) -> dict:
        from movierec_ml.dataops.pipeline import build_gold

        print(f"silver: {silver}")
        return build_gold()

    silver = build_silver(validate_bronze())
    build_gold(silver)


ingest_tmdb()
