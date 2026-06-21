"""Supabase client, schema checks, and shared db helpers."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger("db")

EXPECTED_SCHEMA: dict[str, list[str]] = {
    "guild_rate_notifications": ["guild_id", "channel_id", "role_id"],
    "rate_state": ["id", "previous_rates"],
    "karma_global_settings": ["id", "cooldown_hours", "history_limit"],
    "karma_balances": ["user_id", "balance"],
    "karma_cooldowns": ["giver_id", "receiver_id", "last_given"],
    "karma_events": [
        "user_id",
        "created_at",
        "action",
        "amount",
        "by_name",
        "giver_id",
        "admin_id",
        "reason",
    ],
}

_client: Any = None


def use_supabase() -> bool:
    url = os.environ.get("SUPABASE_URL")
    if not url:
        return False
    if os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY"):
        return True
    return bool(
        os.environ.get("SUPABASE_BOT_JWT")
        and (
            os.environ.get("SUPABASE_PUBLISHABLE_KEY")
            or os.environ.get("SUPABASE_ANON_KEY")
        )
    )


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    if not use_supabase():
        raise RuntimeError("Supabase is not configured (SUPABASE_URL and key required).")
    from db.supabase_client import create_bot_supabase_client

    _client = create_bot_supabase_client()
    return _client


def _tbl(name: str) -> Any:
    return _get_client().table(name)


def check_schema() -> list[tuple[str, bool, Optional[str]]]:
    """Verify EXPECTED_SCHEMA tables exist with required columns."""
    if not EXPECTED_SCHEMA:
        return []
    if not use_supabase():
        return [(name, False, "Supabase not configured") for name in EXPECTED_SCHEMA]

    results: list[tuple[str, bool, Optional[str]]] = []
    try:
        client = _get_client()
    except Exception as exc:
        return [(name, False, str(exc)) for name in EXPECTED_SCHEMA]

    for table, columns in EXPECTED_SCHEMA.items():
        try:
            resp = client.table(table).select(",".join(columns)).limit(1).execute()
            if resp.data is None:
                results.append((table, False, "query returned no data handle"))
            else:
                results.append((table, True, None))
        except Exception as exc:
            results.append((table, False, str(exc)))
    return results
