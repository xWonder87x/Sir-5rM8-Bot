"""Persisted sticky-message id helpers (JSON file + optional STATE_BUCKET)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("commands.common.state")


def _bucket_key(path: Path) -> str:
    return f"state/{path.name}"


def load_persisted_message_id(path: Path) -> int | None:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="ascii"))
            mid = data.get("message_id")
            if mid is not None:
                return int(mid)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.warning("persisted message id load %s: %s", path, e)
    try:
        from functions.blob_state import load_json, state_bucket_configured

        if state_bucket_configured():
            mid = load_json(_bucket_key(path)).get("message_id")
            if mid is not None:
                return int(mid)
    except (ValueError, TypeError, Exception) as e:
        logger.warning("persisted message id bucket load %s: %s", path, e)
    return None


def save_persisted_message_id(path: Path, message_id: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"message_id": str(message_id)}
    path.write_text(json.dumps(payload), encoding="ascii")
    try:
        from functions.blob_state import save_json, state_bucket_configured

        if state_bucket_configured():
            save_json(_bucket_key(path), payload)
    except Exception as e:
        logger.warning("persisted message id bucket save %s: %s", path, e)


def clear_persisted_message_id(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        logger.warning("persisted message id unlink %s: %s", path, e)
    try:
        from functions.blob_state import delete_json, state_bucket_configured

        if state_bucket_configured():
            delete_json(_bucket_key(path))
    except Exception as e:
        logger.warning("persisted message id bucket delete %s: %s", path, e)
