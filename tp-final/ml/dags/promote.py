"""Promoción a PROD desde la UI de Airflow (Trigger DAG w/ config).

    model_version = "dev"  promueve la versión con alias @dev, después de los smoke tests de validate_dev
    model_version = "<n>"  promueve esa versión sin validar en DEV: es el rollback a una versión anterior

Asigna @production, sincroniza el catálogo de PROD y recarga recommender-prod en caliente.
Solo lo dispara el rol ml-engineer (Admin en Airflow): no tiene access_control para otros roles.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(dag_id="promote", schedule=None, start_date=datetime(2026, 1, 1), catchup=False, max_active_runs=1,
     render_template_as_native_obj=True, tags=["release"],
     params={"model_version": Param("dev", type="string",
                                    description="'dev' (versión @dev, valida DEV primero) o un número (rollback)")})
def promote_dag():
    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def promote(model_version: str) -> dict:
        from movierec_ml.release import promote

        result = promote(str(model_version))
        print(result)
        return result

    promote("{{ params.model_version }}")


promote_dag()
