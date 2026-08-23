"""In-memory JSON plus Railway STATE_BUCKET (survives ephemeral disk)."""
from __future__ import annotations

import json
import logging
import threading
from typing import Any

import config
from db import storage

logger = logging.getLogger(__name__)

ASA_CACHE_KEY = "cache/asa.json"
GUILD_LIST_KEY = "state/guild_list_message.json"

_lock = threading.Lock()
_caches: dict[str, dict[str, Any]] = {}
_loaded: set[str] = set()


def state_bucket_configured() -> bool:
    bucket = (getattr(config, "STATE_BUCKET", None) or "").strip()
    return bool(bucket) and storage.use_s3_storage()


def _bucket() -> str:
    return (getattr(config, "STATE_BUCKET", None) or "").strip()


def load_json(key: str) -> dict[str, Any]:
    """Download a JSON object from STATE_BUCKET. Empty dict if missing."""
    bucket = _bucket()
    if not bucket or not storage.use_s3_storage():
        return {}
    try:
        raw = storage.storage_download_bytes(bucket, key)
    except Exception as exc:
        logger.warning("blob_state load %s: %s", key, exc)
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("blob_state invalid JSON %s: %s", key, exc)
        return {}
    return data if isinstance(data, dict) else {}


def save_json(key: str, data: dict[str, Any]) -> bool:
    """Upload a JSON object to STATE_BUCKET. False if storage is unset."""
    bucket = _bucket()
    if not bucket or not storage.use_s3_storage():
        return False
    try:
        body = json.dumps(data, separators=(",", ":"), default=str).encode("utf-8")
        storage.storage_upload_bytes(
            bucket, key, body, content_type="application/json", upsert=True
        )
        return True
    except Exception as exc:
        logger.warning("blob_state save %s: %s", key, exc)
        return False


def delete_json(key: str) -> None:
    bucket = _bucket()
    if not bucket or not storage.use_s3_storage():
        return
    try:
        storage.storage_delete_object(bucket, key)
    except Exception as exc:
        logger.warning("blob_state delete %s: %s", key, exc)


def cache_get(key: str) -> dict[str, Any]:
    with _lock:
        if key not in _loaded:
            _caches[key] = dict(load_json(key))
            _loaded.add(key)
        return dict(_caches[key])


def cache_replace(key: str, data: dict[str, Any], *, flush: bool = True) -> None:
    with _lock:
        _caches[key] = dict(data)
        _loaded.add(key)
        if flush:
            save_json(key, _caches[key])


def reset_blob_state() -> None:
    """Test helper — drop in-memory maps."""
    with _lock:
        _caches.clear()
        _loaded.clear()
