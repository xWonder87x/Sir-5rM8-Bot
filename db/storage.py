"""Railway / S3-compatible object storage (STATE_BUCKET cache)."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from db._base import logger


def _env(*names: str) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def storage_endpoint() -> str:
    return _env(
        "STORAGE_ENDPOINT",
        "AWS_ENDPOINT_URL_S3",
        "AWS_ENDPOINT_URL",
        "S3_ENDPOINT",
    ).rstrip("/")


def storage_region() -> str:
    return _env("STORAGE_REGION", "AWS_REGION", "AWS_DEFAULT_REGION") or "auto"


def use_s3_storage() -> bool:
    """True when an S3 endpoint plus credentials are configured."""
    if not storage_endpoint():
        return False
    if _env("STATE_ACCESS_KEY_ID") and _env("STATE_SECRET_ACCESS_KEY"):
        return True
    return bool(
        _env("AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID")
        and _env("AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY")
    )


def _force_path_style() -> bool:
    raw = _env("STORAGE_FORCE_PATH_STYLE", "AWS_S3_FORCE_PATH_STYLE").lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return False


def _credentials_for_bucket(bucket: str) -> tuple[str, str] | None:
    try:
        import config as cfg
    except Exception:
        cfg = None
    state_bucket = (getattr(cfg, "STATE_BUCKET", None) or "").strip() if cfg else ""
    if state_bucket and state_bucket == (bucket or "").strip():
        key = _env("STATE_ACCESS_KEY_ID")
        secret = _env("STATE_SECRET_ACCESS_KEY")
        if key and secret:
            return key, secret
    key = _env("AWS_ACCESS_KEY_ID", "ACCESS_KEY_ID", "STATE_ACCESS_KEY_ID")
    secret = _env("AWS_SECRET_ACCESS_KEY", "SECRET_ACCESS_KEY", "STATE_SECRET_ACCESS_KEY")
    if key and secret:
        return key, secret
    return None


@lru_cache(maxsize=8)
def _s3_client(access_key: str, secret_key: str) -> Any:
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=storage_endpoint(),
        region_name=storage_region(),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(
            s3={"addressing_style": "path" if _force_path_style() else "virtual"}
        ),
    )


def reset_storage_clients() -> None:
    """Test helper — drop cached boto3 clients."""
    _s3_client.cache_clear()


def storage_upload_bytes(
    bucket: str,
    path: str,
    data: bytes,
    *,
    content_type: str = "application/octet-stream",
    upsert: bool = True,
) -> None:
    del upsert  # S3 put_object always overwrites
    creds = _credentials_for_bucket(bucket)
    if not creds:
        raise RuntimeError(f"No S3 credentials configured for bucket {bucket!r}")
    extra: dict[str, str] = {}
    if content_type:
        extra["ContentType"] = content_type
    _s3_client(*creds).put_object(
        Bucket=bucket, Key=path.lstrip("/"), Body=data, **extra
    )


def storage_download_bytes(bucket: str, path: str) -> bytes | None:
    creds = _credentials_for_bucket(bucket)
    if not creds:
        logger.warning("storage_download_bytes: no S3 credentials for bucket %r", bucket)
        return None
    try:
        resp = _s3_client(*creds).get_object(Bucket=bucket, Key=path.lstrip("/"))
        body = resp.get("Body")
        if body is None:
            return None
        return bytes(body.read())
    except Exception as exc:
        logger.warning("storage_download_bytes %s/%s: %s", bucket, path, exc)
        return None


def storage_delete_object(bucket: str, path: str) -> None:
    creds = _credentials_for_bucket(bucket)
    if not creds:
        return
    try:
        _s3_client(*creds).delete_object(Bucket=bucket, Key=path.lstrip("/"))
    except Exception as exc:
        logger.warning("storage_delete_object %s/%s: %s", bucket, path, exc)
