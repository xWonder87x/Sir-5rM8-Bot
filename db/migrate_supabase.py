"""Import bot state from the legacy Sir-5rM8 Supabase project into ALICE."""
from __future__ import annotations

import os
from typing import Any

from db._base import use_supabase
from db.migrate_json import (
    DatabaseHasDataError,
    MigrationError,
    MigrationResult,
    MigrationSummary,
    SupabaseNotConfiguredError,
    apply_migration_payload,
    database_counts,
)

BATCH_SIZE = 1000

OLD_PROJECT_URL = "https://pplxciubfymklbpvuill.supabase.co"


class OldSupabaseNotConfiguredError(MigrationError):
    """Raised when OLD_SUPABASE_URL / OLD_SUPABASE_SERVICE_KEY are not set."""


class NoOldSupabaseDataError(MigrationError):
    """Raised when the legacy project has no importable rows."""


def _old_credentials() -> tuple[str, str]:
    url = (os.environ.get("OLD_SUPABASE_URL") or OLD_PROJECT_URL).strip()
    key = (
        os.environ.get("OLD_SUPABASE_SERVICE_KEY")
        or os.environ.get("OLD_SUPABASE_KEY")
        or ""
    ).strip()
    if not key:
        raise OldSupabaseNotConfiguredError(
            "Set OLD_SUPABASE_SERVICE_KEY in Railway (secret key or service_role JWT "
            "for the old Sir-5rM8 project pplxciubfymklbpvuill)."
        )
    return url, key


def _old_client():
    from supabase import create_client

    url, key = _old_credentials()
    return create_client(url, key)


def _fetch_all(client, table: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        end = offset + BATCH_SIZE - 1
        resp = client.table(table).select("*").range(offset, end).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < BATCH_SIZE:
            break
        offset += BATCH_SIZE
    return rows


def _event_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": str(record["user_id"]),
        "created_at": record["created_at"],
        "action": record["action"],
        "amount": int(record.get("amount", 1)),
        "by_name": record.get("by_name"),
        "giver_id": record.get("giver_id"),
        "admin_id": record.get("admin_id"),
        "reason": record.get("reason"),
    }


def collect_old_supabase_payload() -> dict[str, Any]:
    client = _old_client()
    client.table("rate_state").select("id").eq("id", 1).limit(1).execute()

    guild_notifications = [
        {
            "guild_id": str(row["guild_id"]),
            "channel_id": str(row["channel_id"]),
            "role_id": str(row["role_id"]),
        }
        for row in _fetch_all(client, "guild_rate_notifications")
    ]
    balances = [
        {"user_id": str(row["user_id"]), "balance": int(row["balance"])}
        for row in _fetch_all(client, "karma_balances")
    ]
    cooldowns = [
        {
            "giver_id": str(row["giver_id"]),
            "receiver_id": str(row["receiver_id"]),
            "last_given": row["last_given"],
        }
        for row in _fetch_all(client, "karma_cooldowns")
    ]
    events = [_event_row(row) for row in _fetch_all(client, "karma_events")]

    settings_resp = (
        client.table("karma_global_settings")
        .select("cooldown_hours, history_limit")
        .eq("id", 1)
        .limit(1)
        .execute()
    )
    if settings_resp.data:
        settings = {
            "cooldown_hours": int(settings_resp.data[0]["cooldown_hours"]),
            "history_limit": int(settings_resp.data[0]["history_limit"]),
        }
    else:
        import config

        settings = {
            "cooldown_hours": config.DEFAULT_COOLDOWN_HOURS,
            "history_limit": config.DEFAULT_KARMA_HISTORY_LIMIT,
        }

    rate_resp = (
        client.table("rate_state")
        .select("previous_rates")
        .eq("id", 1)
        .limit(1)
        .execute()
    )
    rate_state = None
    if rate_resp.data and rate_resp.data[0].get("previous_rates") is not None:
        rate_state = rate_resp.data[0]["previous_rates"]

    return {
        "guild_notifications": guild_notifications,
        "balances": balances,
        "cooldowns": cooldowns,
        "settings": settings,
        "events": events,
        "rate_state": rate_state,
    }


def _source_has_data(payload: dict[str, Any]) -> bool:
    return bool(
        payload["guild_notifications"]
        or payload["balances"]
        or payload["cooldowns"]
        or payload["events"]
        or payload["rate_state"] is not None
    )


def _ensure_ready() -> dict[str, Any]:
    if not use_supabase():
        raise SupabaseNotConfiguredError(
            "ALICE Supabase must be configured (SUPABASE_URL + SUPABASE_SERVICE_KEY)."
        )
    payload = collect_old_supabase_payload()
    if not _source_has_data(payload):
        raise NoOldSupabaseDataError(
            "Legacy Supabase project has no importable rows. "
            "Check OLD_SUPABASE_SERVICE_KEY and that the old project still exists."
        )
    return payload


def preview_old_supabase_migration() -> MigrationSummary:
    return MigrationSummary.from_payload(_ensure_ready())


def run_old_supabase_migration(*, force: bool = False) -> MigrationResult:
    from db.supabase import check_connection

    payload = _ensure_ready()
    source = MigrationSummary.from_payload(payload)
    check_connection()
    apply_migration_payload(payload, force=force)
    return MigrationResult(source=source, database_counts=database_counts())
