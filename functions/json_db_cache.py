"""Durable JSON copies of Neon-backed bot state.

Neon remains authoritative.  This module only avoids repeated reads:
successful database writes update the cache, while the hourly sync compares
cached values with Neon and repairs stale copies.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import config

from functions import blob_state

logger = logging.getLogger(__name__)

VERIFY_SECONDS = 60 * 60
_MISSING = object()
MISSING = _MISSING
_lock = threading.RLock()
_memory: dict[str, Any] = {}
_loaded: set[str] = set()
_verified_at: dict[str, float] = {}


def _local_path(name: str) -> Path:
    return config.DATA_DIR / "cache" / "db" / f"{name}.json"


def _bucket_key(name: str) -> str:
    return f"cache/db/{name}.json"


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _load_local(name: str) -> Any:
    path = _local_path(name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _MISSING
    if isinstance(payload, dict) and payload.get("version") == 1 and "data" in payload:
        return payload["data"]
    return _MISSING


def _load_persisted(name: str) -> Any:
    local = _load_local(name)
    if local is not _MISSING:
        return local
    if blob_state.state_bucket_configured():
        remote = blob_state.load_json(_bucket_key(name))
        if remote.get("version") == 1 and "data" in remote:
            return remote["data"]
    return _MISSING


def _persist(name: str, value: Any) -> None:
    payload = {"version": 1, "data": _copy(value)}
    path = _local_path(name)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":"), default=str), encoding="utf-8")
        os.replace(tmp, path)
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("JSON DB cache save %s: %s", name, exc)
    if blob_state.state_bucket_configured():
        blob_state.save_json(_bucket_key(name), payload)


def has(name: str) -> bool:
    with _lock:
        return name in _loaded or _load_persisted(name) is not _MISSING


def peek(name: str) -> Any:
    """Return the current cache without loading Neon or disk."""
    with _lock:
        if name not in _loaded:
            return _MISSING
        return _copy(_memory[name])


def get(name: str, loader: Callable[[], Any]) -> Any:
    """Get cached data, loading Neon only when no JSON copy exists."""
    with _lock:
        if name in _loaded:
            return _copy(_memory[name])
        persisted = _load_persisted(name)
        if persisted is not _MISSING:
            _memory[name] = persisted
            _loaded.add(name)
            # A restart should use the persisted copy for the next hour.
            _verified_at[name] = time.monotonic()
            return _copy(persisted)
    value = loader()
    put(name, value)
    return _copy(value)


def put(name: str, value: Any) -> None:
    with _lock:
        _memory[name] = _copy(value)
        _loaded.add(name)
        _verified_at[name] = time.monotonic()
    _persist(name, value)


def verify(name: str, loader: Callable[[], Any]) -> bool:
    """Refresh a loaded cache from Neon; return whether the value was equal."""
    with _lock:
        if name not in _loaded:
            return True
    fresh = loader()
    with _lock:
        equal = _memory.get(name) == fresh
    if not equal:
        logger.warning("JSON DB cache repaired from Neon: %s", name)
    put(name, fresh)
    return equal


def verify_due(name: str, loader: Callable[[], Any]) -> bool:
    with _lock:
        due = time.monotonic() - _verified_at.get(name, 0.0) >= VERIFY_SECONDS
    return verify(name, loader) if due else True


def reset() -> None:
    """Test helper; does not delete persisted JSON files."""
    with _lock:
        _memory.clear()
        _loaded.clear()
        _verified_at.clear()
