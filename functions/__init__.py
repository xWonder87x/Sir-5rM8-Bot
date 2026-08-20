"""Shared bot helpers (ASA API, storage orchestration)."""
from __future__ import annotations

import asyncio

import db
from functions.asa import ServerLookupResult, fetch_current_rates, find_server

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


def get_server_channel(guild_id: str) -> dict | None:
    return db.get_rate_notification(guild_id)


def clear_server_channel(guild_id: str) -> bool:
    return db.clear_rate_notification(guild_id)


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

    previous = db.get_previous_rate_values()
    if previous is None:
        db.save_previous_rate_values(current)
        return None, None, None, 1

    if any(previous.get(k) != current.get(k) for k in config.RATE_KEYS):
        db.save_previous_rate_values(current)
        server_list = db.get_rate_notification_channels()
        return server_list, current, previous, 0

    return None, None, None, 1


async def check_rate_changes_async() -> tuple[list | None, dict | None, dict | None, int]:
    return await asyncio.to_thread(check_rate_changes)
