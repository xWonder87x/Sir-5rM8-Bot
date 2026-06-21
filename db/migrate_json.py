"""Import bot state from JSON files under DATA_DIR into Supabase."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from db._base import use_supabase

CONFIG_FILE = config.DATA_DIR / "config.json"
KARMA_HISTORY_FILE = config.DATA_DIR / "karma_history.jsonl"
RATE_STATE_FILE = config.DATA_DIR / "rate_state" / "previous_values.json"

BATCH_SIZE = 200


class MigrationError(Exception):
    """Base class for JSON → Supabase migration failures."""


class SupabaseNotConfiguredError(MigrationError):
    """Raised when Supabase env vars are not set."""


class NoJsonDataError(MigrationError):
    """Raised when there is nothing to import under DATA_DIR."""

    def __init__(self, data_dir: Path | str) -> None:
        super().__init__(
            f"No JSON data found under {data_dir}. "
            "Production data may be in the old Supabase project — use "
            "`/migrate-old-supabase-to-db` instead (set OLD_SUPABASE_SERVICE_KEY in Railway)."
        )


class DatabaseHasDataError(MigrationError):
    """Raised when Supabase already has rows and force=False."""

    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts
        parts = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        super().__init__(
            "Supabase already contains data. Re-run with force=True to upsert over "
            "settings/balances/cooldowns/guilds and append karma events again."
            + (f" ({parts})" if parts else "")
        )


@dataclass(frozen=True)
class MigrationSummary:
    guild_notifications: int
    balances: int
    cooldowns: int
    events: int
    has_rate_state: bool
    cooldown_hours: int
    history_limit: int

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> MigrationSummary:
        settings = payload["settings"]
        return cls(
            guild_notifications=len(payload["guild_notifications"]),
            balances=len(payload["balances"]),
            cooldowns=len(payload["cooldowns"]),
            events=len(payload["events"]),
            has_rate_state=payload["rate_state"] is not None,
            cooldown_hours=int(settings["cooldown_hours"]),
            history_limit=int(settings["history_limit"]),
        )

    def format(self, label: str) -> str:
        return (
            f"**{label}**\n"
            f"Rate notification guilds: {self.guild_notifications}\n"
            f"Karma balances: {self.balances}\n"
            f"Karma cooldowns: {self.cooldowns}\n"
            f"Karma events: {self.events}\n"
            f"Rate state cache: {'yes' if self.has_rate_state else 'no'}\n"
            f"Karma settings: {self.cooldown_hours}h cooldown, "
            f"{self.history_limit} history limit"
        )


@dataclass(frozen=True)
class MigrationResult:
    source: MigrationSummary
    database_counts: dict[str, int]


def json_data_exists() -> bool:
    return (
        CONFIG_FILE.exists()
        or KARMA_HISTORY_FILE.exists()
        or RATE_STATE_FILE.exists()
    )


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


def _load_karma_history_lines() -> list[dict]:
    records: list[dict] = []
    if KARMA_HISTORY_FILE.exists():
        with open(KARMA_HISTORY_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    data = _load_config()
    karma = data.get("karma", {})
    for user_id, entries in karma.get("history", {}).items():
        for entry in entries:
            records.append({"user_id": user_id, **entry})

    return records


def _event_row(record: dict) -> dict:
    return {
        "user_id": str(record["user_id"]),
        "created_at": record["timestamp"],
        "action": record["action"],
        "amount": int(record.get("amount", 1)),
        "by_name": record.get("by"),
        "giver_id": record.get("giver_id"),
        "admin_id": record.get("admin_id"),
        "reason": record.get("reason"),
    }


def collect_json_payload() -> dict[str, Any]:
    data = _load_config()
    karma = data.get("karma", {})

    guild_notifications = []
    for guild_id, guild_data in data.get("guilds", {}).items():
        rn = guild_data.get("rate_notifications")
        if rn:
            guild_notifications.append({
                "guild_id": str(guild_id),
                "channel_id": str(rn["channel_id"]),
                "role_id": str(rn["role_id"]),
            })

    balances = [
        {"user_id": str(user_id), "balance": int(balance)}
        for user_id, balance in karma.get("balances", {}).items()
    ]

    cooldowns = []
    for key, ts in karma.get("cooldowns", {}).items():
        if ":" not in key:
            continue
        giver_id, receiver_id = key.split(":", 1)
        cooldowns.append({
            "giver_id": str(giver_id),
            "receiver_id": str(receiver_id),
            "last_given": ts,
        })

    settings = {
        "cooldown_hours": int(
            karma.get("cooldown_hours", config.DEFAULT_COOLDOWN_HOURS)
        ),
        "history_limit": int(
            karma.get("history_limit", config.DEFAULT_KARMA_HISTORY_LIMIT)
        ),
    }

    events = [_event_row(r) for r in _load_karma_history_lines()]
    rate_state = _load_rate_state()

    return {
        "guild_notifications": guild_notifications,
        "balances": balances,
        "cooldowns": cooldowns,
        "settings": settings,
        "events": events,
        "rate_state": rate_state,
    }


def _sb():
    from db.supabase import _sb as client

    return client()


def database_counts() -> dict[str, int]:
    sb = _sb()
    counts: dict[str, int] = {}
    for table in (
        "guild_rate_notifications",
        "karma_balances",
        "karma_cooldowns",
        "karma_events",
    ):
        r = sb.table(table).select("*", count="exact").limit(0).execute()
        counts[table] = r.count or 0
    r = sb.table("rate_state").select("previous_rates").eq("id", 1).limit(1).execute()
    counts["rate_state_has_data"] = int(
        bool(r.data and r.data[0].get("previous_rates") is not None)
    )
    return counts


def _database_has_data(counts: dict[str, int]) -> bool:
    return bool(
        counts["guild_rate_notifications"]
        or counts["karma_balances"]
        or counts["karma_cooldowns"]
        or counts["karma_events"]
        or counts["rate_state_has_data"]
    )


def _upsert_batches(table: str, rows: list[dict], on_conflict: str) -> None:
    if not rows:
        return
    sb = _sb()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        sb.table(table).upsert(batch, on_conflict=on_conflict).execute()


def _insert_event_batches(rows: list[dict]) -> None:
    if not rows:
        return
    sb = _sb()
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        sb.table("karma_events").insert(batch).execute()


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
    _upsert_batches("karma_balances", payload["balances"], on_conflict="user_id")
    _upsert_batches(
        "karma_cooldowns",
        payload["cooldowns"],
        on_conflict="giver_id,receiver_id",
    )

    sb.table("karma_global_settings").upsert(
        {
            "id": 1,
            "cooldown_hours": payload["settings"]["cooldown_hours"],
            "history_limit": payload["settings"]["history_limit"],
        },
        on_conflict="id",
    ).execute()

    if payload["rate_state"] is not None:
        sb.table("rate_state").upsert(
            {"id": 1, "previous_rates": payload["rate_state"]},
            on_conflict="id",
        ).execute()

    _insert_event_batches(payload["events"])


def apply_migration_payload(payload: dict[str, Any], *, force: bool = False) -> None:
    """Write a collected migration payload into the configured Supabase project."""
    _apply_payload(payload, force=force)


def _ensure_ready() -> dict[str, Any]:
    if not use_supabase():
        raise SupabaseNotConfiguredError(
            "SUPABASE_URL and credentials must be set before importing JSON data."
        )
    if not json_data_exists():
        raise NoJsonDataError(config.DATA_DIR)
    return collect_json_payload()


def preview_migration() -> MigrationSummary:
    payload = _ensure_ready()
    return MigrationSummary.from_payload(payload)


def run_migration(*, force: bool = False) -> MigrationResult:
    from db.supabase import check_connection

    payload = _ensure_ready()
    source = MigrationSummary.from_payload(payload)
    check_connection()
    apply_migration_payload(payload, force=force)
    return MigrationResult(source=source, database_counts=database_counts())
