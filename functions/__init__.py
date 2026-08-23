"""Shared bot helpers (ASA API, storage orchestration)."""
from __future__ import annotations

import asyncio

import db
from functions.asa import ServerLookupResult, fetch_current_rates, find_server
from functions import json_db_cache as cache

__all__ = [
    "ServerLookupResult",
    "add_server_channel",
    "check_rate_changes",
    "check_rate_changes_async",
    "clear_server_channel",
    "fetch_current_rates",
    "fetch_current_rates_async",
    "find_server",
    "find_server_async",
    "get_server_channel",
]


async def find_server_async(query: str) -> ServerLookupResult:
    return await asyncio.to_thread(find_server, query)


async def fetch_current_rates_async() -> dict | None:
    return await asyncio.to_thread(fetch_current_rates)


def add_server_channel(guild_id: str, channel_id: str, role_id: str) -> None:
    db.set_rate_notification(guild_id, channel_id, role_id)
    cache.update(
        "rate_notifications",
        db.get_rate_notification_channels,
        lambda channels: [
            row for row in channels if str(row.get("server_id")) != str(guild_id)
        ]
        + [{"server_id": str(guild_id), "channel_id": str(channel_id), "role": str(role_id)}],
    )


def get_server_channel(guild_id: str) -> dict | None:
    channels = cache.get("rate_notifications", db.get_rate_notification_channels)
    for row in channels:
        if str(row.get("server_id")) == str(guild_id):
            return {"channel_id": row.get("channel_id"), "role_id": row.get("role")}
    return None


def clear_server_channel(guild_id: str) -> bool:
    cleared = db.clear_rate_notification(guild_id)
    if cleared:
        cache.update(
            "rate_notifications",
            db.get_rate_notification_channels,
            lambda channels: [
                row for row in channels if str(row.get("server_id")) != str(guild_id)
            ],
        )
    return cleared


def check_rate_changes() -> tuple[list | None, dict | None, dict | None, int]:
    """
    Check if ASA rates have changed.
    Returns (server_list, current_rates, previous_rates, flag).
    flag=0: rates changed, send notifications. flag=1: no change.
    """
    import config

    current = fetch_current_rates()
    if not current:
        return None, None, None, 1

    previous = cache.get("rate_state", db.get_previous_rate_values)
    if previous is None:
        db.save_previous_rate_values(current)
        cache.put("rate_state", current)
        return None, None, None, 1

    if any(previous.get(k) != current.get(k) for k in config.RATE_KEYS):
        # A change is the only normal-time read-back from Neon.  This protects
        # against a stale cache before sending notifications.
        verified_previous = db.get_previous_rate_values()
        if verified_previous is not None:
            previous = verified_previous
        db.save_previous_rate_values(current)
        cache.put("rate_state", current)
        server_list = cache.get("rate_notifications", db.get_rate_notification_channels)
        return server_list, current, previous, 0

    return None, None, None, 1


async def check_rate_changes_async() -> tuple[list | None, dict | None, dict | None, int]:
    return await asyncio.to_thread(check_rate_changes)


def verify_cached_db_state() -> dict[str, bool]:
    """Hourly Neon reconciliation for every JSON-backed runtime cache."""
    from functions.ark_notices import verify_cached_ark_state
    from functions.bothunter_cache import verify_cached_bothunter_state
    from functions.up_notify_cache import verify_cached_up_notify_state

    try:
        result = {
            "rate_state": cache.verify("rate_state", db.get_previous_rate_values),
            "rate_notifications": cache.verify(
                "rate_notifications", db.get_rate_notification_channels
            ),
        }
        result.update(verify_cached_ark_state())
        result.update(verify_cached_bothunter_state())
        result.update(verify_cached_up_notify_state())
        return result
    finally:
        cache.retry_dirty()
