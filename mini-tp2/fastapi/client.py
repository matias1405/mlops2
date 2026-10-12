"""Cliente de prueba para la API: dispara un caso válido y uno inválido.

Uso:
    python client.py [--base-url http://localhost:8000]
"""
import argparse
import json

import requests

VALID_PAYLOAD = {
    "runtime": 120,
    "budget": 10_000_000,
    "original_language": "en",
    "release_date": "2024-07-15",
    "genres": ["Action", "Comedy"],
    "production_companies": ["Warner Bros."],
    "production_countries": ["United States of America"],
}

# Inválido a propósito: runtime negativo y sin genres (viola gt=0 / min_length=1)
INVALID_PAYLOAD = {
    "runtime": -10,
    "budget": 10_000_000,
    "original_language": "en",
    "release_date": "2024-07-15",
    "genres": [],
    "production_companies": ["Warner Bros."],
    "production_countries": ["United States of America"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    print(f"Health check en {args.base_url}/health ...")
    health = requests.get(f"{args.base_url}/health", timeout=10)
    print(health.status_code, health.json())

    print("\nCaso válido -> POST /v1/predict")
    ok = requests.post(f"{args.base_url}/v1/predict", json=VALID_PAYLOAD, timeout=10)
    print(ok.status_code, json.dumps(ok.json(), indent=2, ensure_ascii=False))
    assert ok.status_code == 200, "Se esperaba 200 para el caso válido"

    print("\nCaso inválido -> POST /v1/predict")
    bad = requests.post(f"{args.base_url}/v1/predict", json=INVALID_PAYLOAD, timeout=10)
    print(bad.status_code, json.dumps(bad.json(), indent=2, ensure_ascii=False))
    assert bad.status_code == 422, "Se esperaba 422 para el caso inválido"

    print("\nOK: la validación rechazó el caso inválido con 422.")


if __name__ == "__main__":
    main()
