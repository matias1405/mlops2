"""Promoción de modelos de DEV a PROD (DAGs validate_dev y promote, operados desde la UI de Airflow).

    validate_dev    smoke tests contra el gateway de DEV (service account qa-bot) + comparación @dev vs @production
                    (F1 por cabeza); el resultado queda en el log de la tarea
    promote         promueve a PROD la versión @dev (después de validate_dev) o una versión explícita (rollback):
                    valida el contrato, asigna @production, sincroniza el catálogo de PROD y pide Reload al
                    recommender-prod (sin reiniciarlo)
"""
import json
import os
import statistics
import time
from datetime import UTC, datetime

MODEL_NAME = "movierec"
METRICS = ("f1_genre", "f1_company", "f1_language", "f1_mean")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _qa_token() -> str:
    import requests

    resp = requests.post(f"{os.environ['KEYCLOAK_INTERNAL_URL']}/realms/platform/protocol/openid-connect/token",
                         data={"grant_type": "client_credentials", "client_id": "qa-bot",
                               "client_secret": os.environ["KC_QA_BOT_SECRET"]}, timeout=15)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _model(alias: str):
    from mlflow import MlflowClient

    client = MlflowClient()
    mv = client.get_model_version_by_alias(MODEL_NAME, alias)
    return mv, client.get_run(mv.run_id).data.metrics


def validate_dev(n_requests: int = 4, p95_ms: int = 2000) -> dict:
    """Smoke tests de DEV. Lanza AssertionError (la tarea falla) si alguno no se cumple."""
    import requests

    base, headers = "http://gateway-dev:8000", {"Authorization": f"Bearer {_qa_token()}"}
    dev, dev_metrics = _model("dev")
    checks = {}

    health = requests.get(f"{base}/api/health", timeout=15).json()
    checks["health_ok"] = health["status"] == "ok"
    checks["serves_dev_alias_version"] = health.get("model", {}).get("version") == str(dev.version)

    onboarding = requests.get(f"{base}/api/movies/onboarding", params={"n": 24}, headers=headers, timeout=60).json()["items"]
    checks["onboarding_24"] = len(onboarding) == 24
    checks["onboarding_posters"] = sum(1 for m in onboarding if m["poster_url"]) >= 20

    # Cada set de semillas se pide dos veces: la primera ("en frío") puede bajar posters nuevos de TMDB
    # (cache-aside) y se reporta aparte; el p95 exigido es el de la segunda, la latencia normal del servicio.
    cold, warm, empty = [], [], 0
    for i in range(n_requests):
        seeds = [m["movie_id"] for m in onboarding[i * 5:(i + 1) * 5]]  # el onboarding exige 5
        for bucket in (cold, warm):
            t0 = time.perf_counter()
            r = requests.post(f"{base}/api/recommendations", json={"movie_ids": seeds, "k": 12}, headers=headers,
                              timeout=60)
            bucket.append((time.perf_counter() - t0) * 1000)
            r.raise_for_status()
            empty += 0 if r.json()["items"] else 1
    p95 = sorted(warm)[max(0, int(len(warm) * 0.95) - 1)]
    checks["recommendations_not_empty"] = empty == 0
    checks[f"latency_p95_lt_{p95_ms}ms"] = p95 < p95_ms
    latencies = warm

    try:
        prod, prod_metrics = _model("production")
        comparison = {k: {"dev": dev_metrics.get(k), "production": prod_metrics.get(k)} for k in METRICS}
        prod_version = prod.version
    except Exception:  # primera promoción: todavía no hay production
        comparison, prod_version = {}, None

    report = {"checked_at": _now(), "dev_version": str(dev.version), "production_version": prod_version,
              "checks": checks,
              "latency_ms": {"p50": round(statistics.median(latencies)), "p95": round(p95),
                             "cold_max_with_poster_fetch": round(max(cold))},
              "metrics": comparison}
    failed = [k for k, ok in checks.items() if not ok]
    print(json.dumps(report, indent=2))
    assert not failed, f"validate_dev falló: {failed}"
    return report


def promote(model_version: str = "dev", *, client=None, validate=None, sync=None, reload=None) -> dict:
    """Promueve a PROD una versión del modelo.

    model_version="dev": la versión con alias @dev, después de los smoke tests de validate_dev.
    model_version="<n>": esa versión, sin validar en DEV (rollback a una versión que ya sirvió en PROD).
    Las dependencias se pueden inyectar para los tests.
    """
    from . import serving_bundle as sb

    if client is None:
        from mlflow import MlflowClient

        client = MlflowClient()
    if sync is None:
        from .catalog_db import sync_catalog as sync
    if reload is None:
        from .serving_client import reload_recommender as reload

    target = str(model_version or "dev").strip()
    validation = None
    if target == "dev":
        mv = client.get_model_version_by_alias(MODEL_NAME, "dev")
        validation = (validate or validate_dev)()
    else:
        if not target.isdigit():
            raise ValueError(f"model_version tiene que ser 'dev' o un número de versión, no {target!r}")
        mv = client.get_model_version(MODEL_NAME, target)
    contract = int(mv.tags.get("contract_version", "0"))
    if contract not in sb.SUPPORTED_CONTRACTS:
        raise RuntimeError(f"contrato {contract} no soportado (soportados: {sorted(sb.SUPPORTED_CONTRACTS)})")
    try:
        previous = client.get_model_version_by_alias(MODEL_NAME, "production").version
    except Exception:
        previous = None
    client.set_registered_model_alias(MODEL_NAME, "production", mv.version)
    client.set_model_version_tag(MODEL_NAME, mv.version, "promoted_at", _now())
    catalog = sync("prod")
    reloaded = reload("prod")
    if reloaded["status"] == "unreachable":
        raise RuntimeError(f"recommender-prod no responde: {reloaded}")
    return {"production": f"{previous} -> {mv.version}", "validated_in_dev": validation is not None,
            "catalog": catalog, "reload": reloaded}
