"""Primera carga de una instalación nueva: descarga -> ingesta -> entrenamiento v1 -> @dev y @production.

Corre sola, una única vez (`@once`), cuando Airflow arranca por primera vez: deja la plataforma con un modelo
servible sin intervención. La fuente del dataset sale de MOVIEREC_BOOTSTRAP_SOURCE (kaggle | local | sample).
Si bronze ya tiene datos, la descarga termina en skipped. Se puede volver a disparar desde la UI.
"""
import os
from datetime import datetime

from airflow.decorators import dag
from airflow.operators.trigger_dagrun import TriggerDagRunOperator


@dag(
    dag_id="bootstrap",
    description="Primera carga: download_tmdb + ingest_tmdb + train_movierec v1 con promote_production",
    schedule="@once",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["mlops"],
)
def bootstrap():
    def trigger(task_id: str, dag_id: str, conf: dict, poke: int) -> TriggerDagRunOperator:
        return TriggerDagRunOperator(task_id=task_id, trigger_dag_id=dag_id, conf=conf, wait_for_completion=True,
                                     poke_interval=poke, allowed_states=["success"], failed_states=["failed"])

    source = os.environ.get("MOVIEREC_BOOTSTRAP_SOURCE", "kaggle")
    download = trigger("download", "download_tmdb", {"source": source}, 15)
    ingest = trigger("ingest", "ingest_tmdb", {}, 15)
    train = trigger("train_v1", "train_movierec",
                    {"config": "v1", "promote_production": True}, 30)
    download >> ingest >> train


bootstrap()
