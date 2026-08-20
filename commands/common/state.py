"""Persisted sticky-message id helpers (JSON file at ``data/*.json``)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("commands.common.state")


def load_persisted_message_id(path: Path) -> int | None:
    try:
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="ascii"))
        mid = data.get("message_id")
        return int(mid) if mid is not None else None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as e:
        logger.warning("persisted message id load %s: %s", path, e)
        return None


def save_persisted_message_id(path: Path, message_id: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"message_id": str(message_id)}), encoding="ascii")
