"""JSON cache wrappers for Bothunter configuration and counters."""
from __future__ import annotations

from typing import Any

import db
from functions import json_db_cache as cache


def _configs() -> dict[str, dict[str, Any]]:
    return cache.get("bothunter_configs", db.get_bothunter_configs)


def get_config(guild_id: str) -> dict | None:
    return _configs().get(str(guild_id))


def set_config(value: dict) -> None:
    db.set_bothunter_config(value)
    configs = _configs()
    configs[str(value["guild_id"])] = dict(value)
    cache.put("bothunter_configs", configs)


def clear_config(guild_id: str) -> bool:
    cleared = db.clear_bothunter_config(guild_id)
    if cleared:
        configs = _configs()
        configs.pop(str(guild_id), None)
        cache.put("bothunter_configs", configs)
    return cleared


def channel_map() -> dict[str, str]:
    return {
        str(cfg["channel_id"]): str(guild_id)
        for guild_id, cfg in _configs().items()
        if cfg.get("channel_id")
    }


def get_count(guild_id: str, channel_id: str | None = None) -> int:
    key = f"bothunter_count:{guild_id}:{channel_id or '*'}"
    return int(cache.get(key, lambda: db.get_bothunter_moderated_count(guild_id, channel_id)) or 0)


def log_event(guild_id: str, user_id: str, channel_id: str | None = None) -> None:
    db.log_bothunter_event(guild_id, user_id, channel_id)
    key = f"bothunter_count:{guild_id}:{channel_id or '*'}"
    cached = cache.peek(key)
    if cached is not cache.MISSING:
        cache.put(key, int(cached or 0) + 1)


def verify_cached_bothunter_state() -> dict[str, bool]:
    result = {"bothunter_configs": cache.verify("bothunter_configs", db.get_bothunter_configs)}
    configs = cache.peek("bothunter_configs")
    if configs is not cache.MISSING:
        for guild_id in configs:
            key = f"bothunter_count:{guild_id}:*"
            if cache.peek(key) is not cache.MISSING:
                result[key] = cache.verify(
                    key, lambda gid=guild_id: db.get_bothunter_moderated_count(gid)
                )
    return result
