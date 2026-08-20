"""Import bot state from JSON files under DATA_DIR into the remote database."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import config
from db._base import use_postgrest

CONFIG_FILE = config.DATA_DIR / "config.json"
RATE_STATE_FILE = config.DATA_DIR / "rate_state" / "previous_values.json"

BATCH_SIZE = 200


class MigrationError(Exception):
    """Base class for JSON → database migration failures."""


class RemoteDbNotConfiguredError(MigrationError):
    """Raised when Postgres REST env vars are not set."""


class NoJsonDataError(MigrationError):
    """Raised when there is nothing to import under DATA_DIR."""


class DatabaseHasDataError(MigrationError):
    """Raised when the remote database already has rows and force=False."""

    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        parts = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        super().__init__(
            "Remote database already contains data. Re-run with force=True to upsert over "
            "guilds and rate state."
            + (f" ({parts})" if parts else "")
        )


@dataclass(frozen=True)
class MigrationSummary:
    guild_notifications: int
    has_rate_state: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> MigrationSummary:
        return cls(
            guild_notifications=len(payload["guild_notifications"]),
            has_rate_state=payload["rate_state"] is not None,
        )

    def format(self, label: str) -> str:
        return (
            f"**{label}**\n"
            f"Rate notification guilds: {self.guild_notifications}\n"
            f"Rate state cache: {'yes' if self.has_rate_state else 'no'}"
        )


@dataclass(frozen=True)
class MigrationResult:
    source: MigrationSummary
    database_counts: dict[str, int]


def json_data_exists() -> bool:
    return CONFIG_FILE.exists() or RATE_STATE_FILE.exists()


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"version": 1, "guilds": {}}
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _load_rate_state() -> dict | None:
    if not RATE_STATE_FILE.exists():
        return None
    with open(RATE_STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def collect_json_payload() -> dict[str, Any]:
    data = _load_config()

    guild_notifications = []
    for guild_id, guild_data in data.get("guilds", {}).items():
        rn = guild_data.get("rate_notifications")
        if rn:
            guild_notifications.append({
                "guild_id": str(guild_id),
                "channel_id": str(rn["channel_id"]),
                "role_id": str(rn["role_id"]),
            })

    return {
        "guild_notifications": guild_notifications,
        "rate_state": _load_rate_state(),
    }


def _sb():
    from db.postgrest import _sb as client

    return client()


def database_counts() -> dict[str, int]:
    sb = _sb()
    counts: dict[str, int] = {}
    r = sb.table("guild_rate_notifications").select("*", count="exact").limit(0).execute()
    counts["guild_rate_notifications"] = r.count or 0
    r = sb.table("rate_state").select("previous_rates").eq("id", 1).limit(1).execute()
    counts["rate_state_has_data"] = int(
        bool(r.data and r.data[0].get("previous_rates") is not None)
    )
    return counts


def _database_has_data(counts: dict[str, int]) -> bool:
    return bool(
        counts["guild_rate_notifications"]
        or counts["rate_state_has_data"]
    )


def _upsert_batches(table: str, rows: list[dict], on_conflict: str) -> None:
    if not rows:
        return
    sb = _sb()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        sb.table(table).upsert(batch, on_conflict=on_conflict).execute()


def _apply_payload(payload: dict[str, Any], *, force: bool) -> None:
    existing = database_counts()
    if _database_has_data(existing) and not force:
        raise DatabaseHasDataError(existing)

    sb = _sb()
    _upsert_batches(
        "guild_rate_notifications",
        payload["guild_notifications"],
        on_conflict="guild_id",
    )

    if payload["rate_state"] is not None:
        sb.table("rate_state").upsert(
            {"id": 1, "previous_rates": payload["rate_state"]},
            on_conflict="id",
        ).execute()


def apply_migration_payload(payload: dict[str, Any], *, force: bool = False) -> None:
    """Write a collected migration payload into the configured remote database."""
    _apply_payload(payload, force=force)


def _ensure_ready() -> dict[str, Any]:
    if not use_postgrest():
        raise RemoteDbNotConfiguredError(
            "POSTGREST_URL and credentials must be set before importing JSON data."
        )
    if not json_data_exists():
        raise NoJsonDataError(f"No JSON data found under {config.DATA_DIR}.")
    return collect_json_payload()


def preview_migration() -> MigrationSummary:
    payload = _ensure_ready()
    return MigrationSummary.from_payload(payload)


def run_migration(*, force: bool = False) -> MigrationResult:
    from db.postgrest import check_connection

    payload = _ensure_ready()
    source = MigrationSummary.from_payload(payload)
    check_connection()
    apply_migration_payload(payload, force=force)
    return MigrationResult(source=source, database_counts=database_counts())
