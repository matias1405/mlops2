"""Configuración por variables de entorno (la misma imagen sirve dev y prod)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_name: str = os.environ.get("MODEL_NAME", "movierec")
    model_alias: str = os.environ.get("MODEL_ALIAS", "dev")
    grpc_port: int = int(os.environ.get("GRPC_PORT", "50051"))
    # Issuer público de Keycloak (iss de los tokens) y JWKS por la red interna.
    jwt_issuer: str = os.environ.get("JWT_ISSUER", "http://localhost:8180/realms/platform")
    jwks_url: str = os.environ.get("JWKS_URL", "http://keycloak:8080/realms/platform/protocol/openid-connect/certs")
    reload_role: str = os.environ.get("RELOAD_REQUIRED_ROLE", "model-deployer")
    # Si al arrancar no hay modelo (alias inexistente / MLflow caído) se reintenta cada N segundos.
    initial_load_retry_s: int = int(os.environ.get("INITIAL_LOAD_RETRY_SECONDS", "30"))
    max_k: int = 100
