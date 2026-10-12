"""Cliente Python para la API GraphQL: pide name, version y metrics del modelo.

Uso:
    python client.py [--base-url http://localhost:8001]
"""
import argparse
import json

import requests

QUERY = """
query GetModel {
  model {
    name
    version
    metrics {
      accuracy
      precision
      recall
      f1
      rocAuc
    }
  }
}
"""


def execute_graphql_query(endpoint: str, query: str, variables: dict | None = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        response = requests.post(endpoint, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        print("Error: no se pudo conectar. ¿Está corriendo el servicio graphql?")
        return {"errors": [{"message": "Connection error"}]}
    except requests.exceptions.HTTPError as http_err:
        print(f"Error HTTP: {http_err} - {response.text}")
        return {"errors": [{"message": str(http_err)}]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8001")
    args = parser.parse_args()
    endpoint = f"{args.base_url}/graphql"

    print(f"--- Consultando metadatos del modelo en {endpoint} ---")
    result = execute_graphql_query(endpoint, QUERY)

    if "data" in result:
        print(json.dumps(result["data"], indent=2, ensure_ascii=False))
    elif "errors" in result:
        print(f"Errores: {result['errors']}")


if __name__ == "__main__":
    main()
