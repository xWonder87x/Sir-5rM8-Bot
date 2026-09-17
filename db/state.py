"""Key/value JSON runtime state (kill switch)."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from db._base import use_postgres

logger = logging.getLogger("db.state")

STATE_TABLE = "bot_runtime_state"


def killswitch_key() -> str:
    return "killswitch"


def get_state_sync(key: str) -> dict[str, Any]:
    if not use_postgres():
        return {}
    from db.postgres import get_runtime_state_sync

    return get_runtime_state_sync(key)


def set_state_sync(key: str, value: dict[str, Any]) -> None:
    if not use_postgres():
        raise RuntimeError("bot_runtime_state requires DATABASE_URL")
    from db.postgres import set_runtime_state_sync

    set_runtime_state_sync(key, value)


async def get_state(key: str) -> dict[str, Any]:
    return await asyncio.to_thread(get_state_sync, key)


async def set_state(key: str, value: dict[str, Any]) -> None:
    await asyncio.to_thread(set_state_sync, key, value)
