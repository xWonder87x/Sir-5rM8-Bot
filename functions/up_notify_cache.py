"""JSON cache wrappers for pending server-up notification subscriptions."""
from __future__ import annotations

import db
from functions import json_db_cache as cache


def _watchers() -> list[dict]:
    return cache.get("up_notify", db.list_up_notify_watchers_all)


def list_keys() -> list[str]:
    return sorted({str(row["server_key"]) for row in _watchers() if row.get("server_key")})


def list_watchers(server_key: str) -> list[dict]:
    key = str(server_key).strip()
    return [row for row in _watchers() if str(row.get("server_key")) == key]


def add(
    server_key: str,
    user_id: str,
    channel_id: str,
    guild_id: str | None = None,
    query: str | None = None,
    session_name: str | None = None,
) -> bool:
    added = db.add_up_notify(
        server_key, user_id, channel_id, guild_id, query, session_name
    )
    if added:
        new_watcher = {
            "server_key": str(server_key),
            "user_id": str(user_id),
            "channel_id": str(channel_id),
            "guild_id": guild_id,
            "query": query,
            "session_name": session_name,
        }
        cache.update(
            "up_notify",
            db.list_up_notify_watchers_all,
            lambda watchers: [
                row
                for row in watchers
                if not (
                    str(row.get("server_key")) == str(server_key)
                    and str(row.get("user_id")) == str(user_id)
                    and str(row.get("channel_id")) == str(channel_id)
                )
            ]
            + [new_watcher],
        )
    return added


def clear(server_key: str, channel_id: str | None = None) -> int:
    cleared = db.clear_up_notify(server_key, channel_id)
    if cleared:
        key = str(server_key).strip()
        cache.update(
            "up_notify",
            db.list_up_notify_watchers_all,
            lambda watchers: [
                row
                for row in watchers
                if not (
                    str(row.get("server_key")) == key
                    and (
                        channel_id is None
                        or str(row.get("channel_id")) == str(channel_id)
                    )
                )
            ],
        )
    return cleared


def verify_cached_up_notify_state() -> dict[str, bool]:
    return {"up_notify": cache.verify("up_notify", db.list_up_notify_watchers_all)}
