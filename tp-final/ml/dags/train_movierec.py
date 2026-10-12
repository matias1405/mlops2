"""DAG de entrenamiento: gold/training -> clasificador de 2 salidas (PyTorch) -> embeddings de app_catalog
-> MLflow registry -> gate -> @dev.

Parámetros:
    config              v1 | v2 | v3 | v4 (ml/configs/<config>.yaml)
    promote_production  solo para bootstrap: además de @dev asigna @production
    git_sha             commit del código que entrena (tag del run); vacío = MOVIEREC_GIT_SHA del entorno
Si el gate asigna @dev, se pide Reload al recommender-dev (gRPC, service account airflow-deployer).
Antes del Reload se sincroniza el catálogo del ambiente (app_<env>.catalog) que usa el api-gateway.
"""
import os
from datetime import datetime

from airflow.decorators import dag, task
from airflow.models.param import Param

TRAINER_PYTHON = os.environ.get("TRAINER_PYTHON", "/opt/venvs/trainer/bin/python")


@dag(
    dag_id="train_movierec",
    description="Entrena el recomendador, lo registra en MLflow y lo promueve a @dev si pasa el gate",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    render_template_as_native_obj=True,
    # Separación de roles: además de Admin, solo DataScientist puede disparar este DAG.
    access_control={"DataScientist": {"can_read", "can_edit"}},
    tags=["mlops"],
    params={
        "config": Param("v1", enum=["v1", "v2", "v3", "v4"]),
        "promote_production": Param(False, type="boolean"),
        "git_sha": Param("", type="string"),
    },
)
def train_movierec():
    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def train_and_register(config: str, git_sha: str) -> dict:
        import os

        from movierec_ml.training.pipeline import train_and_register

        if git_sha:
            os.environ["MOVIEREC_GIT_SHA"] = git_sha
        return train_and_register(config)

    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def gate_and_alias(trained: dict, promote_production: bool) -> dict:
        from movierec_ml.training.pipeline import gate_and_alias

        return gate_and_alias(trained, promote_production)

    @task.external_python(python=TRAINER_PYTHON, expect_airflow=False)
    def reload_recommenders(decision: dict) -> list:
        from movierec_ml.catalog_db import sync_catalog
        from movierec_ml.serving_client import reload_recommender

        envs = [{"dev": "dev", "production": "prod"}[a] for a in decision["aliases"]]
        if not envs:
            print(f"gate no aprobado ({decision}): no se recarga ningún ambiente")
        results = []
        for env in envs:
            print(sync_catalog(env))  # primero el catálogo: el gateway tiene que conocer los ids nuevos
            results.append(reload_recommender(env))
        for r in results:
            print(r)
        return results

    trained = train_and_register("{{ params.config }}", "{{ params.git_sha }}")
    decision = gate_and_alias(trained, "{{ params.promote_production }}")
    reload_recommenders(decision)


train_movierec()
