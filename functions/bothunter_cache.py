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
    cache.update(
        "bothunter_configs",
        db.get_bothunter_configs,
        lambda configs: {**configs, str(value["guild_id"]): dict(value)},
    )


def clear_config(guild_id: str) -> bool:
    cleared = db.clear_bothunter_config(guild_id)
    if cleared:
        cache.update(
            "bothunter_configs",
            db.get_bothunter_configs,
            lambda configs: {
                key: value for key, value in configs.items() if key != str(guild_id)
            },
        )
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
    aggregate_key = f"bothunter_count:{guild_id}:*"
    cache.update_loaded(aggregate_key, lambda count: int(count or 0) + 1)
    if channel_id is not None:
        channel_key = f"bothunter_count:{guild_id}:{channel_id}"
        cache.update_loaded(channel_key, lambda count: int(count or 0) + 1)


def verify_cached_bothunter_state() -> dict[str, bool]:
    result = {"bothunter_configs": cache.verify("bothunter_configs", db.get_bothunter_configs)}
    prefix = "bothunter_count:"
    for key in cache.diagnostics_snapshot():
        if not key.startswith(prefix):
            continue
        guild_id, channel_id = key[len(prefix):].rsplit(":", 1)
        result[key] = cache.verify(
            key,
            lambda gid=guild_id, cid=channel_id: db.get_bothunter_moderated_count(
                gid, None if cid == "*" else cid
            ),
        )
    return result
