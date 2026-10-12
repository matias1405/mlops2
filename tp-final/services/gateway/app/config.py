"""Configuración del gateway por variables de entorno (misma imagen en dev y prod)."""
import os
from dataclasses import dataclass, field


def _csv(name: str, default: str) -> frozenset[str]:
    return frozenset(x.strip() for x in os.environ.get(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    env_name: str = os.environ.get("ENV_NAME", "dev")
    # Base de la app del ambiente (app_dev / app_prod), usuario propio.
    db_dsn: str = (f"host={os.environ.get('APP_DB_HOST', 'postgres')} dbname={os.environ.get('APP_DB_NAME', 'app_dev')} "
                   f"user={os.environ.get('APP_DB_NAME', 'app_dev')} password={os.environ.get('APP_DB_PASSWORD', '')}")
    recommender_target: str = os.environ.get("RECOMMENDER_TARGET", "recommender:50051")
    # Posters: cache-aside en MinIO con el usuario gateway-<env> (solo bucket posters).
    s3_endpoint: str = os.environ.get("S3_ENDPOINT_URL", "http://minio:9000")
    s3_access_key: str = os.environ.get("MINIO_GATEWAY_USER", "")
    s3_secret_key: str = os.environ.get("MINIO_GATEWAY_SECRET", "")
    poster_bucket: str = os.environ.get("POSTER_BUCKET", "posters")
    poster_size: str = os.environ.get("POSTER_SIZE", "w342")
    tmdb_image_base: str = os.environ.get("TMDB_IMAGE_BASE", "https://image.tmdb.org/t/p")
    poster_concurrency: int = int(os.environ.get("POSTER_CONCURRENCY", "10"))
    poster_timeout_s: float = float(os.environ.get("POSTER_TIMEOUT_SECONDS", "8"))
    public_media_prefix: str = os.environ.get("PUBLIC_MEDIA_PREFIX", "/media")
    # Auth: realm del ambiente (prod: movierec, dev: platform).
    auth_issuer: str = os.environ.get("AUTH_ISSUER", "http://localhost:8180/realms/platform")
    jwks_url: str = os.environ.get("JWKS_URL", "http://keycloak:8080/realms/platform/protocol/openid-connect/certs")
    allowed_clients: frozenset[str] = field(default_factory=lambda: _csv("AUTH_ALLOWED_CLIENTS", "movierec-web-dev"))
    required_roles: frozenset[str] = field(default_factory=lambda: _csv("AUTH_REQUIRED_ROLES", "app-developer"))
    rate_limit: str = os.environ.get("RATE_LIMIT_RECOMMENDATIONS", "60/minute")
    # El onboarding exige exactamente esta cantidad de películas elegidas.
    required_picks: int = 5
    max_k: int = 50
