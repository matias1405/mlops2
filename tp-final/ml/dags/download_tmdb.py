"""DAG de descarga única del dataset TMDB a bronze (DataOps), sin credenciales.

    bronze_is_empty    si bronze ya tiene el CSV, termina en skipped
    download_to_bronze baja el CSV en la versión vigente de Kaggle, verifica el tamaño y lo sube a
                       bronze/tmdb/TMDB_movie_dataset_v11.csv

Parámetro source: kaggle (API pública) | local (data/raw/) | sample (data/sample/, CI y demo).
Bronze es inmutable: para bajar otra versión hay que vaciarlo a mano (operación excepcional, ver README).
"""
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(
    dag_id="download_tmdb",
    description="Descarga única del dataset TMDB a bronze (Kaggle sin credenciales)",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    render_template_as_native_obj=True,
    access_control={"DataScientist": {"can_read", "can_edit"}},
    tags=["dataops"],
    params={"source": Param("kaggle", enum=["kaggle", "local", "sample"])},
)
def download_tmdb():
    @task.short_circuit
    def bronze_is_empty() -> bool:
        import subprocess

        # Corre en el venv del trainer (boto3); short_circuit necesita un bool en el worker de Airflow.
        out = subprocess.run([TRAINER_PYTHON, "-c", "from movierec_ml.dataops.pipeline import bronze_is_empty as f; "
                              "print(f())"], capture_output=True, text=True, check=True)
        print(out.stdout)
        return out.stdout.strip().splitlines()[-1] == "True"

    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def download_to_bronze(source: str) -> dict:
        from movierec_ml.dataops.pipeline import download_to_bronze

        return download_to_bronze(source)

    bronze_is_empty() >> download_to_bronze("{{ params.source }}")


download_tmdb()
