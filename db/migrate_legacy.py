"""Import bot state from a legacy Sir-5rM8 Postgres REST project into Discord Bots."""
from __future__ import annotations

import os
from typing import Any

from db._base import use_postgrest
from db.migrate_json import (
    MigrationError,
    MigrationResult,
    MigrationSummary,
    RemoteDbNotConfiguredError,
    apply_migration_payload,
    database_counts,
)

BATCH_SIZE = 1000

OLD_PROJECT_URL = "https://pplxciubfymklbpvuill.supabase.co"


class LegacyDbNotConfiguredError(MigrationError):
    """Raised when LEGACY_DB_URL / LEGACY_DB_KEY are not set."""


class NoLegacyDbDataError(MigrationError):
    """Raised when the legacy project has no importable rows."""


def _old_credentials() -> tuple[str, str]:
    url = (
        os.environ.get("LEGACY_DB_URL")
        or os.environ.get("OLD_SUPABASE_URL")
        or OLD_PROJECT_URL
    ).strip()
    key = (
        os.environ.get("LEGACY_DB_KEY")
        or os.environ.get("OLD_SUPABASE_SERVICE_KEY")
        or os.environ.get("OLD_SUPABASE_KEY")
        or ""
    ).strip()
    if not key:
        raise LegacyDbNotConfiguredError(
            "Set LEGACY_DB_KEY (secret key or service_role JWT for the old Sir-5rM8 project)."
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


def collect_legacy_payload() -> dict[str, Any]:
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
        "rate_state": rate_state,
    }


def _source_has_data(payload: dict[str, Any]) -> bool:
    return bool(
        payload["guild_notifications"]
        or payload["rate_state"] is not None
    )


def _ensure_ready() -> dict[str, Any]:
    if not use_postgrest():
        raise RemoteDbNotConfiguredError(
            "Discord Bots Postgres REST must be configured (POSTGREST_URL + POSTGREST_KEY)."
        )
    payload = collect_legacy_payload()
    if not _source_has_data(payload):
        raise NoLegacyDbDataError(
            "Legacy database has no importable rows. "
            "Check LEGACY_DB_KEY and that the old project still exists."
        )
    return payload


def preview_legacy_migration() -> MigrationSummary:
    return MigrationSummary.from_payload(_ensure_ready())


def run_legacy_migration(*, force: bool = False) -> MigrationResult:
    from db.postgrest import check_connection

    payload = _ensure_ready()
    source = MigrationSummary.from_payload(payload)
    check_connection()
    apply_migration_payload(payload, force=force)
    return MigrationResult(source=source, database_counts=database_counts())
