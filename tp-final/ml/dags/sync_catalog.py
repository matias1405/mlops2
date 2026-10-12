"""Sincroniza el catálogo de un ambiente (app_<env>.catalog) con el modelo de su alias.

Lo usa el api-gateway para el onboarding y para enriquecer las recomendaciones. Corre solo dentro de
train_movierec (dev) y promote (prod); este DAG sirve para correrlo a mano o en el bootstrap.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(dag_id="sync_catalog", schedule=None, start_date=datetime(2026, 1, 1), catchup=False,
     render_template_as_native_obj=True, tags=["mlops"],
     access_control={"DataScientist": {"can_read", "can_edit"}},
     params={"env": Param("dev", enum=["dev", "prod"])})
def sync_catalog_dag():
    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def sync(env: str) -> dict:
        from movierec_ml.catalog_db import sync_catalog

        return sync_catalog(env)

    sync("{{ params.env }}")


sync_catalog_dag()
