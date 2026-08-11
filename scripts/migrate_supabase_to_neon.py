#!/usr/bin/env python3
"""
Apply Sir-5rM8 schema to Neon and optionally copy data from Supabase.

Usage:
  # Set DATABASE_URL to your Neon connection string first.
  python scripts/migrate_supabase_to_neon.py --apply-schema
  python scripts/migrate_supabase_to_neon.py                 # dry-run counts from Supabase
  python scripts/migrate_supabase_to_neon.py --apply         # copy data
  python scripts/migrate_supabase_to_neon.py --apply --force
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA_FILE = ROOT / "neon" / "schema.sql"


def _collect_from_supabase() -> dict:
    """Read current Supabase tables using the REST client (needs SUPABASE_* env)."""
    import os

    # Temporarily prefer Supabase even if DATABASE_URL is set.
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("NEON_DATABASE_URL", None)

    # Clear cached imports that may have already bound to postgres.
    for mod in list(sys.modules):
        if mod == "db" or mod.startswith("db."):
            del sys.modules[mod]

    from db.supabase_client import create_bot_supabase_client
    from db._base import use_supabase

    if not use_supabase():
        raise SystemExit(
            "Supabase credentials required to export data "
            "(SUPABASE_URL + SUPABASE_SERVICE_KEY)."
        )

    sb = create_bot_supabase_client()

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
        import config

        settings = {
            "cooldown_hours": config.DEFAULT_COOLDOWN_HOURS,
            "history_limit": config.DEFAULT_KARMA_HISTORY_LIMIT,
        }

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
    parser = argparse.ArgumentParser(description="Migrate Sir-5rM8 from Supabase to Neon.")
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Create tables/functions on Neon (DATABASE_URL).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy data from Supabase into Neon.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow import when Neon already has rows.",
    )
    args = parser.parse_args()

    import os

    db_url = (os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL") or "").strip()
    if (args.apply_schema or args.apply) and not db_url:
        print(
            "Set DATABASE_URL to your Neon connection string first.",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.apply_schema:
        from db.postgres import apply_schema

        sql = SCHEMA_FILE.read_text(encoding="utf-8")
        apply_schema(sql)
        print(f"Applied schema from {SCHEMA_FILE}")
        if not args.apply:
            print("\nSchema applied. Re-run with --apply to copy data from Supabase.")
            return

    # Dry-run or --apply: export from Supabase then optionally import.
    saved_url = os.environ.get("DATABASE_URL")
    saved_neon = os.environ.get("NEON_DATABASE_URL")
    try:
        payload = _collect_from_supabase()
    finally:
        if saved_url is not None:
            os.environ["DATABASE_URL"] = saved_url
        elif "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        if saved_neon is not None:
            os.environ["NEON_DATABASE_URL"] = saved_neon
        elif "NEON_DATABASE_URL" in os.environ:
            del os.environ["NEON_DATABASE_URL"]
        for mod in list(sys.modules):
            if mod == "db" or mod.startswith("db."):
                del sys.modules[mod]

    _print_payload(payload, "Supabase source")

    if not args.apply:
        print("\nDry run only — re-run with --apply to copy into Neon.")
        return

    from db.postgres import database_counts, import_payload

    import_payload(payload, force=args.force)
    print("\nMigration applied successfully.")
    print("Neon row counts:", database_counts())
    print(
        "\nNext steps:\n"
        "  1. Keep DATABASE_URL in .env / Railway (Supabase vars become unused).\n"
        "  2. Restart the bot — expect: Storage backend: Postgres/Neon\n"
        "  3. Smoke test /rate_channel_status and /manage_karma action:check"
    )


if __name__ == "__main__":
    main()
