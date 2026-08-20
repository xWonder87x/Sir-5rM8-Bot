#!/usr/bin/env python3
"""
Apply Sir-5rM8 schema to Postgres and optionally copy data from Postgres REST.

Usage:
  # Set DATABASE_URL to your Postgres connection string first.
  python scripts/migrate_to_postgres.py --apply-schema
  python scripts/migrate_to_postgres.py                 # dry-run counts from REST
  python scripts/migrate_to_postgres.py --apply         # copy data
  python scripts/migrate_to_postgres.py --apply --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

SCHEMA_FILE = ROOT / "postgres" / "schema.sql"


def _collect_from_postgrest() -> dict:
    """Read current REST tables (needs POSTGREST_* / legacy REST env)."""
    from db._base import get_postgrest_key, get_postgrest_url
    from supabase import create_client

    url = get_postgrest_url()
    key = get_postgrest_key()
    if not url or not key:
        raise SystemExit(
            "Postgres REST credentials required to export data "
            "(POSTGREST_URL + POSTGREST_KEY)."
        )

    sb = create_client(url, key)

    def fetch_all(table: str) -> list[dict]:
        rows: list[dict] = []
        offset = 0
        batch_size = 1000
        while True:
            end = offset + batch_size - 1
            resp = sb.table(table).select("*").range(offset, end).execute()
            batch = resp.data or []
            rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return rows

    guilds = [
        {
            "guild_id": str(r["guild_id"]),
            "channel_id": str(r["channel_id"]),
            "role_id": str(r["role_id"]),
        }
        for r in fetch_all("guild_rate_notifications")
    ]
    balances = [
        {"user_id": str(r["user_id"]), "balance": int(r["balance"])}
        for r in fetch_all("karma_balances")
    ]
    cooldowns = [
        {
            "giver_id": str(r["giver_id"]),
            "receiver_id": str(r["receiver_id"]),
            "last_given": r["last_given"],
        }
        for r in fetch_all("karma_cooldowns")
    ]
    events = []
    for r in fetch_all("karma_events"):
        events.append({
            "user_id": str(r["user_id"]),
            "created_at": r["created_at"],
            "action": r["action"],
            "amount": int(r.get("amount", 1)),
            "by_name": r.get("by_name"),
            "giver_id": r.get("giver_id"),
            "admin_id": r.get("admin_id"),
            "reason": r.get("reason"),
        })

    settings_resp = (
        sb.table("karma_global_settings")
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
        settings = {"cooldown_hours": 24, "history_limit": 10}

    rate_resp = (
        sb.table("rate_state").select("previous_rates").eq("id", 1).limit(1).execute()
    )
    rate_state = None
    if rate_resp.data and rate_resp.data[0].get("previous_rates") is not None:
        rate_state = rate_resp.data[0]["previous_rates"]

    return {
        "guild_notifications": guilds,
        "balances": balances,
        "cooldowns": cooldowns,
        "settings": settings,
        "events": events,
        "rate_state": rate_state,
    }


def _print_payload(payload: dict, label: str) -> None:
    print(f"\n{label}")
    print(f"  Rate notification guilds: {len(payload['guild_notifications'])}")
    print(f"  Karma balances:           {len(payload['balances'])}")
    print(f"  Karma cooldowns:          {len(payload['cooldowns'])}")
    print(f"  Karma events:             {len(payload['events'])}")
    print(f"  Rate state cache:         {'yes' if payload['rate_state'] else 'no'}")
    print(
        f"  Karma settings:           "
        f"{payload['settings']['cooldown_hours']}h / "
        f"{payload['settings']['history_limit']} history"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate Sir-5rM8 to Postgres.")
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Create tables/functions on Postgres (DATABASE_URL).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy data from Postgres REST into Postgres.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow import when Postgres already has rows.",
    )
    args = parser.parse_args()

    from db._base import get_database_url

    db_url = get_database_url()
    if (args.apply_schema or args.apply) and not db_url:
        print(
            "Set DATABASE_URL to your Postgres connection string first.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.apply_schema:
        from db.postgres import apply_schema

        sql = SCHEMA_FILE.read_text(encoding="utf-8")
        apply_schema(sql)
        print(f"Applied schema from {SCHEMA_FILE}")
        if not args.apply:
            print("\nSchema applied. Re-run with --apply to copy data from Postgres REST.")
            return

    # Dry-run or --apply: export from REST then optionally import.
    payload = _collect_from_postgrest()
    _print_payload(payload, "Postgres REST source")

    if not args.apply:
        print("\nDry run only — re-run with --apply to copy into Postgres.")
        return

    from db.postgres import database_counts, import_payload

    import_payload(payload, force=args.force)
    print("\nMigration applied successfully.")
    print("Postgres row counts:", database_counts())
    print(
        "\nNext steps:\n"
        "  1. Keep DATABASE_URL in .env / the host (REST vars become unused).\n"
        "  2. Restart the bot — expect: Storage backend: Postgres\n"
        "  3. Smoke test /rate_channel_status and /manage_karma action:check"
    )


if __name__ == "__main__":
    main()
