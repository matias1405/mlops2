"""Valida DEV antes de una release: smoke tests contra el api-gateway de DEV (service account qa-bot)
y comparación de métricas @dev vs @production. El reporte queda en gold/reports/validate_dev/.

También lo corre `promote` antes de pasar @dev a PROD: si falla, no hay promoción.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(dag_id="validate_dev", schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     tags=["release"])
def validate_dev_dag():
    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def smoke_tests() -> dict:
        from movierec_ml.release import validate_dev

        return validate_dev()

    smoke_tests()


validate_dev_dag()
