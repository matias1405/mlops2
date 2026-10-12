"""Acceso al data lake (MinIO/S3) con el usuario del servicio que corre la tarea.

La configuración llega por variables de entorno (S3_ENDPOINT_URL, LAKE_ACCESS_KEY,
LAKE_SECRET_KEY): pasar de MinIO a S3 es cambiar esas variables.
"""
import os
import tempfile
from pathlib import Path

BRONZE, SILVER, GOLD = "bronze", "silver", "gold"
CACHE_DIR = Path(os.environ.get("MOVIEREC_CACHE_DIR", "/tmp/movierec-cache"))


def s3_client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
        aws_access_key_id=os.environ["LAKE_ACCESS_KEY"],
        aws_secret_access_key=os.environ["LAKE_SECRET_KEY"],
    )


def exists(s3, bucket: str, key: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def download_cached(s3, bucket: str, key: str) -> Path:
    """Baja un objeto a una cache local indexada por su ETag (evita re-bajar 600 MB por tarea)."""
    etag = s3.head_object(Bucket=bucket, Key=key)["ETag"].strip('"')
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = CACHE_DIR / f"{bucket}-{etag}{Path(key).suffix}"
    if not target.exists():
        tmp = target.with_suffix(".part")
        s3.download_file(bucket, key, str(tmp))
        tmp.rename(target)
    return target


def put_parquet(s3, df, bucket: str, key: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "movies.parquet"
        df.to_parquet(out, index=False)
        s3.upload_file(str(out), bucket, key)
