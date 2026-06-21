#!/usr/bin/env python3
"""
Migrate Sir-5rM8 data from local JSON files to Supabase.

Usage:
  python scripts/migrate_json_to_supabase.py              # dry run (default)
  python scripts/migrate_json_to_supabase.py --apply      # write to Supabase
  python scripts/migrate_json_to_supabase.py --apply --force  # overwrite existing DB rows

Stop the bot before migrating so JSON files are not being written mid-import.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Project root on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from db.supabase import _sb, check_connection  # noqa: E402

CONFIG_FILE = config.DATA_DIR / "config.json"
KARMA_HISTORY_FILE = config.DATA_DIR / "karma_history.jsonl"
RATE_STATE_FILE = config.DATA_DIR / "rate_state" / "previous_values.json"

BATCH_SIZE = 200


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


def _collect_payload() -> dict:
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


def _db_counts() -> dict[str, int]:
    sb = _sb()
    counts = {}
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


def _print_summary(payload: dict, label: str) -> None:
    print(f"\n{label}")
    print(f"  Rate notification guilds: {len(payload['guild_notifications'])}")
    print(f"  Karma balances:           {len(payload['balances'])}")
    print(f"  Karma cooldowns:          {len(payload['cooldowns'])}")
    print(f"  Karma events (history):   {len(payload['events'])}")
    print(f"  Rate state cache:         {'yes' if payload['rate_state'] else 'no'}")
    print(
        f"  Karma settings:           "
        f"{payload['settings']['cooldown_hours']}h cooldown, "
        f"{payload['settings']['history_limit']} history limit"
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


def _apply(payload: dict, force: bool) -> None:
    sb = _sb()
    existing = _db_counts()
    has_data = (
        existing["guild_rate_notifications"]
        or existing["karma_balances"]
        or existing["karma_cooldowns"]
        or existing["karma_events"]
        or existing["rate_state_has_data"]
    )
    if has_data and not force:
        print(
            "\nSupabase already contains data. Re-run with --force to upsert over "
            "settings/balances/cooldowns/guilds and append karma events again, "
            "or clear tables manually in Supabase first.",
            file=sys.stderr,
        )
        sys.exit(1)

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
    print("\nMigration applied successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate JSON bot data to Supabase.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write data to Supabase (default is dry run only).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow migration when Supabase already has rows.",
    )
    args = parser.parse_args()

    if not config.USE_SUPABASE:
        print(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env before migrating.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not CONFIG_FILE.exists() and not KARMA_HISTORY_FILE.exists() and not RATE_STATE_FILE.exists():
        print("No JSON data found under data/. Nothing to migrate.", file=sys.stderr)
        sys.exit(1)

    payload = _collect_payload()
    _print_summary(payload, "JSON source")

    if not args.apply:
        print("\nDry run only — no changes written. Re-run with --apply to migrate.")
        return

    print("\nConnecting to Supabase...")
    check_connection()
    _apply(payload, force=args.force)
    _print_summary(_collect_payload(), "After migration (source unchanged)")
    print("\nDatabase row counts:", _db_counts())
    print(
        "\nNext steps:\n"
        "  1. Verify counts look correct in Supabase Table Editor.\n"
        "  2. Restart the bot with SUPABASE_URL + SUPABASE_SERVICE_KEY in .env.\n"
        "  3. Confirm startup log shows: Storage backend: Supabase ... connection OK\n"
        "  4. Keep JSON files as backup until you are satisfied, then archive them."
    )


if __name__ == "__main__":
    main()
