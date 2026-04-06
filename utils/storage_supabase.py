"""
Supabase (PostgreSQL) storage. Enable with SUPABASE_URL + SUPABASE_SERVICE_KEY in .env.
Run docs/supabase_schema.sql in the Supabase SQL editor first.
"""
from __future__ import annotations

from datetime import datetime, timezone

from supabase import Client, create_client

from utils import config

_client: Client | None = None

DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24


def _sb() -> Client:
    global _client
    if _client is None:
        assert config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _client


def _ensure_karma_settings_row() -> None:
    sb = _sb()
    r = sb.table("karma_global_settings").select("id").eq("id", 1).limit(1).execute()
    if not r.data:
        sb.table("karma_global_settings").insert({
            "id": 1,
            "cooldown_hours": DEFAULT_COOLDOWN_HOURS,
            "history_limit": DEFAULT_KARMA_HISTORY_LIMIT,
        }).execute()


def _ensure_rate_state_row() -> None:
    sb = _sb()
    r = sb.table("rate_state").select("id").eq("id", 1).limit(1).execute()
    if not r.data:
        sb.table("rate_state").insert({"id": 1, "previous_rates": None}).execute()


def set_rate_notification(guild_id: str, channel_id: str, role_id: str) -> None:
    _sb().table("guild_rate_notifications").upsert(
        {"guild_id": guild_id, "channel_id": channel_id, "role_id": role_id},
        on_conflict="guild_id",
    ).execute()


def get_rate_notification(guild_id: str) -> dict | None:
    r = _sb().table("guild_rate_notifications").select("channel_id, role_id").eq("guild_id", guild_id).limit(1).execute()
    if not r.data:
        return None
    row = r.data[0]
    return {"channel_id": row["channel_id"], "role_id": row["role_id"]}


def clear_rate_notification(guild_id: str) -> bool:
    r = _sb().table("guild_rate_notifications").delete().eq("guild_id", guild_id).execute()
    return bool(r.data)


def get_rate_notification_channels() -> list[dict]:
    r = _sb().table("guild_rate_notifications").select("guild_id, channel_id, role_id").execute()
    return [
        {"server_id": row["guild_id"], "channel_id": row["channel_id"], "role": row["role_id"]}
        for row in (r.data or [])
    ]


def get_previous_rate_values() -> dict | None:
    _ensure_rate_state_row()
    r = _sb().table("rate_state").select("previous_rates").eq("id", 1).limit(1).execute()
    if not r.data or r.data[0].get("previous_rates") is None:
        return None
    return r.data[0]["previous_rates"]


def save_previous_rate_values(values: dict) -> None:
    _ensure_rate_state_row()
    _sb().table("rate_state").update({"previous_rates": values}).eq("id", 1).execute()


def get_karma_settings() -> dict:
    _ensure_karma_settings_row()
    r = _sb().table("karma_global_settings").select("cooldown_hours, history_limit").eq("id", 1).limit(1).execute()
    if not r.data:
        return {"cooldown_hours": DEFAULT_COOLDOWN_HOURS, "history_limit": DEFAULT_KARMA_HISTORY_LIMIT}
    row = r.data[0]
    return {
        "cooldown_hours": row.get("cooldown_hours") or DEFAULT_COOLDOWN_HOURS,
        "history_limit": row.get("history_limit") or DEFAULT_KARMA_HISTORY_LIMIT,
    }


def karma_get_balance(user_id: str) -> int:
    r = _sb().table("karma_balances").select("balance").eq("user_id", user_id).limit(1).execute()
    if not r.data:
        return 0
    return int(r.data[0].get("balance") or 0)


def karma_get_cooldown(giver_id: str, receiver_id: str) -> datetime | None:
    r = _sb().table("karma_cooldowns").select("last_given").eq("giver_id", giver_id).eq("receiver_id", receiver_id).limit(1).execute()
    if not r.data:
        return None
    ts = r.data[0].get("last_given")
    if not ts:
        return None
    if isinstance(ts, str):
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    else:
        dt = ts
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def karma_add(giver_id: str, receiver_id: str, giver_name: str, reason: str) -> int:
    sb = _sb()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    bal_r = sb.table("karma_balances").select("balance").eq("user_id", receiver_id).limit(1).execute()
    new_bal = int(bal_r.data[0]["balance"]) + 1 if bal_r.data else 1
    sb.table("karma_balances").upsert(
        {"user_id": receiver_id, "balance": new_bal},
        on_conflict="user_id",
    ).execute()

    sb.table("karma_cooldowns").upsert(
        {"giver_id": giver_id, "receiver_id": receiver_id, "last_given": now_iso},
        on_conflict="giver_id,receiver_id",
    ).execute()

    sb.table("karma_events").insert({
        "user_id": receiver_id,
        "created_at": now_iso,
        "action": "add",
        "amount": 1,
        "by_name": giver_name,
        "giver_id": giver_id,
        "admin_id": None,
        "reason": reason,
    }).execute()

    return new_bal


def karma_take(target_id: str, admin_id: str, admin_name: str) -> int | None:
    sb = _sb()
    bal_r = sb.table("karma_balances").select("balance").eq("user_id", target_id).limit(1).execute()
    balance = int(bal_r.data[0]["balance"]) if bal_r.data else 0
    if balance <= 0:
        return None
    new_bal = balance - 1
    sb.table("karma_balances").upsert(
        {"user_id": target_id, "balance": new_bal},
        on_conflict="user_id",
    ).execute()
    now_iso = datetime.now(timezone.utc).isoformat()
    sb.table("karma_events").insert({
        "user_id": target_id,
        "created_at": now_iso,
        "action": "remove",
        "amount": 1,
        "by_name": admin_name,
        "giver_id": None,
        "admin_id": admin_id,
        "reason": None,
    }).execute()
    return new_bal


def _event_row_to_history_dict(row: dict) -> dict:
    ts = row.get("created_at")
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    return {
        "timestamp": ts,
        "action": row["action"],
        "amount": row.get("amount", 1),
        "by": row.get("by_name") or "?",
        "giver_id": row.get("giver_id"),
        "admin_id": row.get("admin_id"),
        "reason": row.get("reason"),
    }


def karma_get_history(user_id: str) -> list[dict]:
    limit = get_karma_settings()["history_limit"]
    r = _sb().table("karma_events").select(
        "created_at, action, amount, by_name, giver_id, admin_id, reason"
    ).eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    rows = r.data or []
    return [_event_row_to_history_dict(row) for row in rows]


def karma_get_audit(limit: int = 20) -> list[dict]:
    r = _sb().table("karma_events").select(
        "user_id, created_at, action, amount, by_name, giver_id, admin_id, reason"
    ).eq("action", "remove").order("created_at", desc=True).limit(limit).execute()
    out = []
    for row in r.data or []:
        ts = row.get("created_at")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        out.append({
            "user_id": row["user_id"],
            "timestamp": ts,
            "action": row["action"],
            "amount": row.get("amount", 1),
            "by": row.get("by_name") or "?",
            "admin_id": row.get("admin_id"),
        })
    return out
