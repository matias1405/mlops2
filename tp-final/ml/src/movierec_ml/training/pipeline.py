"""Pasos del DAG train_movierec: entrenar + registrar en MLflow y gate de promoción a @dev.

    gold/training     -> entrenamiento del clasificador (split train/val/test por id)
    gold/app_catalog  -> pasada hacia adelante con los pesos finales: solo esas películas van al bundle

Modelos registrados:
    movierec          pyfunc con el bundle de serving (lo que consume el recommender)
    movierec-encoder  encoder PyTorch + vocabulario + normalización tabular (para re-embeber películas nuevas)
Aliases: @dev (candidato en DEV) y @production (servido en PROD).
"""
import json
import os
import tempfile
from pathlib import Path

import yaml

from ..dataops.pipeline import load_gold

MODEL_NAME = "movierec"
ENCODER_NAME = "movierec-encoder"
EXPERIMENT = "movierec"
GATE_METRIC = "f1_genre"  # la única cabeza común a las cuatro configs
CONFIG_DIR = Path(os.environ.get("MOVIEREC_CONFIG_DIR", "/opt/airflow/ml/configs"))


def load_config(name: str) -> dict:
    return yaml.safe_load((CONFIG_DIR / f"{name}.yaml").read_text())


def _flatten(d: dict, prefix: str = "") -> dict:
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, f"{key}."))
        else:
            out[key] = v if not isinstance(v, list) else ",".join(map(str, v))
    return out


def train_and_register(config_name: str, max_rows: int | None = None) -> dict:
    import mlflow
    import mlflow.pytorch
    from mlflow import MlflowClient

    from .. import serving_bundle as sb
    from .evaluation import evaluate, heads_tag, loggable
    from .train import embed, fit

    cfg = load_config(config_name)
    training = load_gold("training")
    app = load_gold("app_catalog")
    if not set(app["id"]) <= set(training["id"]):
        raise ValueError("gold/app_catalog no es un subconjunto de gold/training: correr ingest_tmdb de nuevo")
    if max_rows:  # solo para pruebas rápidas
        training = training.sort_values("vote_count", ascending=False).head(max_rows).reset_index(drop=True)
        app = app[app["id"].isin(training["id"])].reset_index(drop=True)
    dataset = {"rows": len(training), "app_catalog_rows": len(app)}
    git_sha = os.environ.get("MOVIEREC_GIT_SHA", "unknown")

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=cfg["name"]) as run:
        result = fit(cfg, training)
        heads = heads_tag(result)
        mlflow.set_tags({"config": cfg["name"], "git_sha": git_sha, "contract_version": sb.CONTRACT_VERSION,
                         "heads": heads})
        mlflow.log_params(_flatten(cfg))
        mlflow.log_params({"dataset.rows": len(training), "dataset.app_catalog_rows": len(app)})
        for h in result.history:
            mlflow.log_metrics({k: v for k, v in h.items() if k != "epoch"}, step=h["epoch"])
        metrics = evaluate(result, training, cfg)
        mlflow.log_metrics({**loggable(metrics), "best_epoch": result.best_epoch})
        mlflow.log_dict({**metrics, "heads": heads, "best_epoch": result.best_epoch}, "evaluation/metrics.json")

        # Embeddings: pasada hacia adelante con los pesos finales, solo por las películas recomendables.
        features = training.set_index("id").loc[app["id"]].reset_index()
        embeddings = embed(result.model, result.inputs(features, cfg))
        bundle_catalog = app.reset_index(drop=True)
        mlflow.log_text(sb.model_card(cfg, metrics, heads, dataset, training,
                                      sb.examples(embeddings, bundle_catalog)), "model_card.md")

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            # Encoder + lo necesario para re-embeber películas nuevas sin reentrenar.
            meta = tmp / "encoder_meta"
            meta.mkdir()
            (meta / "vocab.json").write_text(json.dumps(result.vocab.itos))
            (meta / "tabular.json").write_text(json.dumps(result.tabular.to_json()))
            (meta / "targets.json").write_text(json.dumps({t.column: {"kind": t.kind, "classes": t.classes}
                                                           for t in result.targets}))
            (meta / "config.json").write_text(json.dumps(cfg))
            mlflow.pytorch.log_model(result.model, "encoder", registered_model_name=ENCODER_NAME,
                                     extra_files=[str(p) for p in meta.iterdir()], pip_requirements=["torch==2.5.1"])
            # Bundle de serving (contrato v1) como modelo pyfunc.
            bundle = sb.write_bundle(tmp / "bundle", embeddings, bundle_catalog["id"], {
                "model_config": cfg["name"], "text_columns": cfg["text_columns"], "dataset": dataset,
                "git_sha": git_sha, "mlflow_run_id": run.info.run_id,
            })
            info = mlflow.pyfunc.log_model(
                "movierec", python_model=sb.MovieRecModel(), artifacts={"bundle": str(bundle)},
                code_paths=[str(Path(sb.__file__).parent)], registered_model_name=MODEL_NAME,
                pip_requirements=["numpy", "pandas", "pyarrow"],
            )

    client = MlflowClient()
    version = info.registered_model_version
    for key, value in {"contract_version": str(sb.CONTRACT_VERSION), "config": cfg["name"], "heads": heads}.items():
        client.set_model_version_tag(MODEL_NAME, version, key, value)
    return {"run_id": run.info.run_id, "model_version": str(version), "config": cfg["name"],
            "gate_metric": GATE_METRIC, "metrics": metrics, "n_movies": len(app)}


def gate_and_alias(trained: dict, promote_production: bool = False, tolerance: float = 0.0) -> dict:
    """Asigna @dev si f1_genre no empeora respecto de @production.

    promote_production=True (solo bootstrap) asigna además @production a esta versión.
    """
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    client = MlflowClient()
    metric = trained["gate_metric"]
    candidate = trained["metrics"][metric]
    try:
        prod = client.get_model_version_by_alias(MODEL_NAME, "production")
        prod_value = client.get_run(prod.run_id).data.metrics.get(metric)
    except MlflowException:
        prod, prod_value = None, None

    version = trained["model_version"]
    vs = f"{metric}={candidate:.4f} vs production={'n/a' if prod_value is None else f'{prod_value:.4f}'}"
    if promote_production:
        passed, reason = True, f"forced (promote_production: nueva línea de base): {vs}"
    elif prod_value is None:
        passed, reason = True, f"passed (no hay production): {vs}"
    else:
        passed = candidate >= prod_value - tolerance
        reason = f"{'passed' if passed else 'failed'}: {vs}"
    client.set_model_version_tag(MODEL_NAME, version, "gate", reason)
    aliases = []
    if passed:
        client.set_registered_model_alias(MODEL_NAME, "dev", version)
        aliases.append("dev")
        if promote_production:
            client.set_registered_model_alias(MODEL_NAME, "production", version)
            aliases.append("production")
    return {"model_version": version, "passed": passed, "candidate": candidate,
            "production_version": prod.version if prod else None, "production_value": prod_value,
            "aliases": aliases}
