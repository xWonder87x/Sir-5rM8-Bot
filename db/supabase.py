"""Supabase (PostgreSQL) storage backend."""
from __future__ import annotations

from datetime import datetime, timezone

import config
from db._base import _get_client


def _sb():
    return _get_client()


def check_connection() -> None:
    """Verify Supabase is reachable (DNS, URL, auth). Raises on failure."""
    _sb().table("rate_state").select("id").eq("id", 1).limit(1).execute()


def _rpc_int(result) -> int | None:
    data = result.data
    if data is None:
        return None
    if isinstance(data, list):
        return int(data[0]) if data else None
    return int(data)


def _ensure_karma_settings_row() -> None:
    sb = _sb()
    r = sb.table("karma_global_settings").select("id").eq("id", 1).limit(1).execute()
    if not r.data:
        sb.table("karma_global_settings").insert({
            "id": 1,
            "cooldown_hours": config.DEFAULT_COOLDOWN_HOURS,
            "history_limit": config.DEFAULT_KARMA_HISTORY_LIMIT,
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
    if get_rate_notification(guild_id) is None:
        return False
    _sb().table("guild_rate_notifications").delete().eq("guild_id", guild_id).execute()
    return True


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
        return {
            "cooldown_hours": config.DEFAULT_COOLDOWN_HOURS,
            "history_limit": config.DEFAULT_KARMA_HISTORY_LIMIT,
        }
    row = r.data[0]
    return {
        "cooldown_hours": row.get("cooldown_hours") or config.DEFAULT_COOLDOWN_HOURS,
        "history_limit": row.get("history_limit") or config.DEFAULT_KARMA_HISTORY_LIMIT,
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
    now_iso = datetime.now(timezone.utc).isoformat()

    new_bal = _rpc_int(sb.rpc("karma_increment_balance", {"p_user_id": receiver_id}).execute())
    if new_bal is None:
        raise RuntimeError(
            "karma_increment_balance failed — re-run supabase/schema.sql in Supabase SQL Editor"
        )

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
    new_bal = _rpc_int(sb.rpc("karma_decrement_balance", {"p_user_id": target_id}).execute())
    if new_bal is None:
        return None

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


# --- Bothunter ---

def _bothunter_row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    experiments = row.get("experiments") or []
    if isinstance(experiments, str):
        import json
        try:
            experiments = json.loads(experiments)
        except (json.JSONDecodeError, TypeError):
            experiments = []
    return {
        "guild_id": str(row["guild_id"]),
        "channel_id": str(row["channel_id"]) if row.get("channel_id") else None,
        "log_channel_id": str(row["log_channel_id"]) if row.get("log_channel_id") else None,
        "action": row.get("action") or "softban",
        "warning_msg_id": str(row["warning_msg_id"]) if row.get("warning_msg_id") else None,
        "experiments": list(experiments),
        "warning_message": row.get("warning_message"),
        "dm_message": row.get("dm_message"),
        "log_message": row.get("log_message"),
        "reinvite_code": row.get("reinvite_code"),
    }


def get_bothunter_config(guild_id: str) -> dict | None:
    r = _sb().table("bothunter_config").select("*").eq("guild_id", str(guild_id)).limit(1).execute()
    rows = r.data or []
    return _bothunter_row_to_dict(rows[0] if rows else None)


def set_bothunter_config(config: dict) -> None:
    payload = {
        "guild_id": str(config["guild_id"]),
        "channel_id": config.get("channel_id"),
        "log_channel_id": config.get("log_channel_id"),
        "action": config.get("action") or "softban",
        "warning_msg_id": config.get("warning_msg_id"),
        "experiments": list(config.get("experiments") or []),
        "warning_message": config.get("warning_message"),
        "dm_message": config.get("dm_message"),
        "log_message": config.get("log_message"),
        "reinvite_code": config.get("reinvite_code"),
    }
    _sb().table("bothunter_config").upsert(payload, on_conflict="guild_id").execute()


def clear_bothunter_config(guild_id: str) -> bool:
    r = _sb().table("bothunter_config").delete().eq("guild_id", str(guild_id)).execute()
    return bool(r.data)


def log_bothunter_event(guild_id: str, user_id: str, channel_id: str | None = None) -> None:
    _sb().table("bothunter_events").insert({
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "channel_id": str(channel_id) if channel_id else None,
    }).execute()


def get_bothunter_moderated_count(guild_id: str, channel_id: str | None = None) -> int:
    q = _sb().table("bothunter_events").select("id", count="exact").eq("guild_id", str(guild_id))
    if channel_id:
        q = q.eq("channel_id", str(channel_id))
    r = q.execute()
    return int(r.count or 0)


def get_bothunter_channel_map() -> dict[str, str]:
    r = _sb().table("bothunter_config").select("guild_id, channel_id").not_.is_("channel_id", "null").execute()
    out: dict[str, str] = {}
    for row in r.data or []:
        if row.get("channel_id"):
            out[str(row["channel_id"])] = str(row["guild_id"])
    return out


# --- Server player sampling ---

def watch_server(server_key: str, session_name: str | None = None) -> None:
    key = str(server_key).strip()
    if not key:
        return
    from datetime import datetime, timezone

    import config

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "server_key": key,
        "session_name": session_name,
        "last_queried": now,
    }
    _sb().table("server_watchlist").upsert(payload, on_conflict="server_key").execute()
    r = _sb().table("server_watchlist").select("server_key", count="exact").execute()
    overflow = int(r.count or 0) - config.SERVER_WATCHLIST_MAX
    if overflow > 0:
        old = (
            _sb()
            .table("server_watchlist")
            .select("server_key")
            .order("last_queried", desc=False)
            .limit(overflow)
            .execute()
            .data
            or []
        )
        for row in old:
            _sb().table("server_watchlist").delete().eq("server_key", row["server_key"]).execute()


def record_server_sample(
    server_key: str,
    num_players: int,
    max_players: int,
    *,
    sampled_at=None,
) -> None:
    key = str(server_key).strip()
    if not key:
        return
    from datetime import datetime, timezone

    ts = sampled_at or datetime.now(timezone.utc)
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    _sb().table("server_watchlist").upsert(
        {"server_key": key, "last_queried": ts},
        on_conflict="server_key",
    ).execute()
    _sb().table("server_player_samples").insert({
        "server_key": key,
        "num_players": int(num_players),
        "max_players": int(max_players),
        "sampled_at": ts,
    }).execute()


def get_server_player_history(server_key: str, *, hours: int | None = None) -> list[dict]:
    key = str(server_key).strip()
    if not key:
        return []
    from datetime import datetime, timedelta, timezone

    import config

    window = hours if hours is not None else config.SERVER_HISTORY_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=int(window))
    r = (
        _sb()
        .table("server_player_samples")
        .select("num_players, max_players, sampled_at")
        .eq("server_key", key)
        .gte("sampled_at", cutoff.isoformat())
        .order("sampled_at", desc=False)
        .execute()
    )
    out: list[dict] = []
    for row in r.data or []:
        ts = row.get("sampled_at")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        out.append({
            "num_players": int(row["num_players"]),
            "max_players": int(row["max_players"]),
            "sampled_at": ts,
        })
    return out


def list_watched_server_keys() -> list[str]:
    r = (
        _sb()
        .table("server_watchlist")
        .select("server_key")
        .order("last_queried", desc=True)
        .execute()
    )
    return [str(row["server_key"]) for row in (r.data or [])]


def prune_server_samples(*, retention_days: int | None = None) -> int:
    from datetime import datetime, timedelta, timezone

    import config

    days = retention_days if retention_days is not None else config.SERVER_SAMPLE_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
    r = (
        _sb()
        .table("server_player_samples")
        .delete()
        .lt("sampled_at", cutoff.isoformat())
        .execute()
    )
    return len(r.data or [])


def add_up_notify(
    server_key: str,
    user_id: str,
    channel_id: str,
    guild_id: str | None = None,
    query: str | None = None,
    session_name: str | None = None,
) -> bool:
    key = str(server_key).strip()
    uid = str(user_id).strip()
    cid = str(channel_id).strip()
    if not key or not uid or not cid:
        return False
    existing = (
        _sb()
        .table("server_up_notify")
        .select("user_id")
        .eq("server_key", key)
        .eq("user_id", uid)
        .eq("channel_id", cid)
        .limit(1)
        .execute()
    )
    if existing.data:
        return False
    _sb().table("server_up_notify").insert({
        "server_key": key,
        "user_id": uid,
        "channel_id": cid,
        "guild_id": str(guild_id) if guild_id else None,
        "query": query,
        "session_name": session_name,
    }).execute()
    return True


def list_up_notify_keys() -> list[str]:
    r = _sb().table("server_up_notify").select("server_key").execute()
    keys = sorted({str(row["server_key"]) for row in (r.data or []) if row.get("server_key")})
    return keys


def list_up_notify_watchers(server_key: str) -> list[dict]:
    key = str(server_key).strip()
    if not key:
        return []
    r = (
        _sb()
        .table("server_up_notify")
        .select("server_key, user_id, channel_id, guild_id, query, session_name")
        .eq("server_key", key)
        .execute()
    )
    out: list[dict] = []
    for row in r.data or []:
        out.append({
            "server_key": str(row.get("server_key") or key),
            "user_id": str(row.get("user_id") or ""),
            "channel_id": str(row.get("channel_id") or ""),
            "guild_id": row.get("guild_id"),
            "query": row.get("query"),
            "session_name": row.get("session_name"),
        })
    return out


def clear_up_notify(server_key: str, channel_id: str | None = None) -> int:
    key = str(server_key).strip()
    if not key:
        return 0
    q = _sb().table("server_up_notify").delete().eq("server_key", key)
    if channel_id:
        q = q.eq("channel_id", str(channel_id))
    r = q.execute()
    return len(r.data or [])
