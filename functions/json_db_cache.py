"""Durable JSON copies of database-backed bot state.

The configured database remains authoritative. Persisted copies may serve
during startup grace, but reconciliation only refreshes them from the database.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import config

from functions import blob_state

logger = logging.getLogger(__name__)

ENVELOPE_VERSION = 2
_MISSING = object()
MISSING = _MISSING
_state_lock = threading.RLock()
_key_locks: dict[str, threading.RLock] = {}
_memory: dict[str, Any] = {}
_metadata: dict[str, dict[str, Any]] = {}
_loaded: set[str] = set()
_verified_at: dict[str, float] = {}
_dirty: set[str] = set()
_stats: dict[str, int] = {
    "memory_hits": 0,
    "local_hits": 0,
    "bucket_hits": 0,
    "db_hits": 0,
    "repairs": 0,
    "persistence_failures": 0,
    "persistence_retries": 0,
}


@dataclass(frozen=True)
class _PersistedCopy:
    data: Any
    written_at: float
    version: int
    source: str
    generation: str


def _local_path(name: str) -> Path:
    return config.DATA_DIR / "cache" / "db" / f"{name}.json"


def _bucket_key(name: str) -> str:
    return f"cache/db/{name}.json"


def _copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _key_lock(name: str) -> threading.RLock:
    with _state_lock:
        return _key_locks.setdefault(name, threading.RLock())


def _increment(counter: str) -> None:
    with _state_lock:
        _stats[counter] += 1


def _decode_envelope(
    payload: Any, *, source: str, fallback_written_at: float = 0.0
) -> _PersistedCopy | None:
    if not isinstance(payload, dict) or "data" not in payload:
        return None
    version = payload.get("version")
    if version == 1:
        return _PersistedCopy(
            data=payload["data"],
            written_at=fallback_written_at,
            version=1,
            source=source,
            generation="v1",
        )
    if version != ENVELOPE_VERSION:
        return None
    written_at = payload.get("written_at")
    if not isinstance(written_at, (int, float)):
        return None
    generation = payload.get("generation")
    return _PersistedCopy(
        data=payload["data"],
        written_at=float(written_at),
        version=ENVELOPE_VERSION,
        source=source,
        generation=str(generation or ""),
    )


def _load_local(name: str) -> _PersistedCopy | None:
    path = _local_path(name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        modified_at = path.stat().st_mtime
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return _decode_envelope(payload, source="local", fallback_written_at=modified_at)


def _load_bucket(name: str) -> _PersistedCopy | None:
    if not blob_state.state_bucket_configured():
        return None
    return _decode_envelope(
        blob_state.load_json(_bucket_key(name)),
        source="bucket",
    )


def _load_persisted(name: str) -> _PersistedCopy | None:
    local = _load_local(name)
    remote = _load_bucket(name)
    valid = [item for item in (local, remote) if item is not None]
    if not valid:
        return None
    selected = max(valid, key=lambda item: (item.written_at, item.version))
    _increment(f"{selected.source}_hits")
    return selected


def _new_envelope(value: Any, *, source: str) -> dict[str, Any]:
    return {
        "version": ENVELOPE_VERSION,
        "written_at": time.time(),
        "generation": uuid.uuid4().hex,
        "source": source,
        "data": _copy(value),
    }


def _persist_envelope(name: str, payload: dict[str, Any]) -> bool:
    path = _local_path(name)
    temp_path: Path | None = None
    local_ok = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, separators=(",", ":"), default=str)
        os.replace(temp_path, path)
        local_ok = True
    except (OSError, TypeError, ValueError) as exc:
        logger.warning("JSON DB cache save %s: %s", name, exc)
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
    bucket_ok = True
    if blob_state.state_bucket_configured():
        bucket_ok = blob_state.save_json(_bucket_key(name), payload)
    ok = local_ok and bucket_ok
    with _state_lock:
        if ok:
            _dirty.discard(name)
        else:
            _dirty.add(name)
            _stats["persistence_failures"] += 1
    return ok


def _store_locked(name: str, value: Any, *, source: str) -> bool:
    payload = _new_envelope(value, source=source)
    with _state_lock:
        if name in _dirty:
            _stats["persistence_retries"] += 1
        _memory[name] = _copy(value)
        _metadata[name] = {
            "source": source,
            "written_at": payload["written_at"],
            "version": payload["version"],
            "generation": payload["generation"],
        }
        _loaded.add(name)
        _verified_at[name] = time.monotonic()
    return _persist_envelope(name, payload)


def _get_locked(name: str, loader: Callable[[], Any]) -> Any:
    with _state_lock:
        if name in _loaded:
            _stats["memory_hits"] += 1
            return _copy(_memory[name])
    persisted = _load_persisted(name)
    if persisted is not None:
        with _state_lock:
            _memory[name] = _copy(persisted.data)
            _metadata[name] = {
                "source": persisted.source,
                "written_at": persisted.written_at,
                "version": persisted.version,
                "generation": persisted.generation,
            }
            _loaded.add(name)
        return _copy(persisted.data)
    value = loader()
    _increment("db_hits")
    _store_locked(name, value, source="database")
    return _copy(value)


def has(name: str) -> bool:
    with _key_lock(name):
        with _state_lock:
            if name in _loaded:
                return True
        return _load_persisted(name) is not None


def peek(name: str) -> Any:
    """Return the current cache without loading Neon or disk."""
    with _state_lock:
        if name not in _loaded:
            return _MISSING
        return _copy(_memory[name])


def get(name: str, loader: Callable[[], Any]) -> Any:
    """Get cached data, loading Neon only when no JSON copy exists."""
    with _key_lock(name):
        return _get_locked(name, loader)


def put(name: str, value: Any) -> bool:
    """Replace a cache value after a successful database write."""
    with _key_lock(name):
        return _store_locked(name, value, source="database-write")


def update(
    name: str,
    loader: Callable[[], Any],
    mutator: Callable[[Any], Any],
) -> Any:
    """Atomically load, mutate, and persist one key in this process.

    ``mutator`` may mutate its argument in place and return ``None``, or return
    a replacement value.
    """
    with _key_lock(name):
        current = _get_locked(name, loader)
        working = _copy(current)
        replacement = mutator(working)
        value = working if replacement is None else replacement
        _store_locked(name, value, source="database-write")
        return _copy(value)


def update_loaded(name: str, mutator: Callable[[Any], Any]) -> bool:
    """Atomically mutate a key only when a memory or persisted copy exists."""
    with _key_lock(name):
        with _state_lock:
            loaded = name in _loaded
        if not loaded:
            persisted = _load_persisted(name)
            if persisted is None:
                return False
            with _state_lock:
                _memory[name] = _copy(persisted.data)
                _metadata[name] = {
                    "source": persisted.source,
                    "written_at": persisted.written_at,
                    "version": persisted.version,
                    "generation": persisted.generation,
                }
                _loaded.add(name)
        with _state_lock:
            working = _copy(_memory[name])
        replacement = mutator(working)
        value = working if replacement is None else replacement
        _store_locked(name, value, source="database-write")
        return True


def verify(name: str, loader: Callable[[], Any]) -> bool:
    """Refresh a loaded cache from the database; return whether it was equal."""
    with _key_lock(name):
        with _state_lock:
            if name not in _loaded:
                return True
        fresh = loader()
        _increment("db_hits")
        with _state_lock:
            equal = _memory.get(name) == fresh
        if not equal:
            logger.warning("JSON DB cache repaired from database: %s", name)
            _increment("repairs")
        _store_locked(name, fresh, source="database-reconcile")
        return equal


def verify_due(name: str, loader: Callable[[], Any]) -> bool:
    verify_seconds = float(getattr(config, "JSON_CACHE_RECONCILE_SECONDS", 60 * 60))
    with _state_lock:
        due = time.monotonic() - _verified_at.get(name, 0.0) >= verify_seconds
    return verify(name, loader) if due else True


def retry_dirty() -> dict[str, bool]:
    """Retry failed local/bucket writes using the latest in-memory values."""
    with _state_lock:
        names = sorted(_dirty)
    result: dict[str, bool] = {}
    for name in names:
        with _key_lock(name):
            with _state_lock:
                if name not in _loaded:
                    _dirty.discard(name)
                    continue
                value = _copy(_memory[name])
                meta = dict(_metadata[name])
                _stats["persistence_retries"] += 1
            payload = {
                "version": ENVELOPE_VERSION,
                "written_at": meta["written_at"],
                "generation": meta["generation"],
                "source": meta["source"],
                "data": value,
            }
            result[name] = _persist_envelope(name, payload)
    return result


def stats_snapshot() -> dict[str, int]:
    """Return process-local cache counters; no database writes are involved."""
    with _state_lock:
        snapshot = dict(_stats)
        snapshot["loaded_keys"] = len(_loaded)
        snapshot["dirty_keys"] = len(_dirty)
        return snapshot


def diagnostics_snapshot() -> dict[str, dict[str, Any]]:
    """Return source and age metadata for loaded keys."""
    now = time.time()
    with _state_lock:
        return {
            name: {
                **dict(_metadata[name]),
                "age_seconds": max(0.0, now - float(_metadata[name]["written_at"])),
                "dirty": name in _dirty,
            }
            for name in sorted(_loaded)
        }


def reset() -> None:
    """Test helper; does not delete persisted JSON files."""
    with _state_lock:
        _memory.clear()
        _metadata.clear()
        _loaded.clear()
        _verified_at.clear()
        _dirty.clear()
        for key in _stats:
            _stats[key] = 0
