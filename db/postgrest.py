"""Postgres REST storage backend."""
from __future__ import annotations

import config
from db._base import _get_client


def _sb():
    return _get_client()


def check_connection() -> None:
    """Verify Postgres REST is reachable (DNS, URL, auth). Raises on failure."""
    _sb().table("rate_state").select("id").eq("id", 1).limit(1).execute()


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


def _ensure_ark_notice_state_row() -> None:
    sb = _sb()
    r = sb.table("ark_notification_state").select("id").eq("id", 1).limit(1).execute()
    if not r.data:
        sb.table("ark_notification_state").insert({"id": 1, "previous_text": None}).execute()


def set_ark_notification(guild_id: str, channel_id: str) -> None:
    existing = get_ark_notification(guild_id)
    payload: dict = {"guild_id": guild_id, "channel_id": channel_id}
    if existing and existing.get("channel_id") == channel_id and existing.get("last_message_id"):
        payload["last_message_id"] = existing["last_message_id"]
    elif existing and existing.get("channel_id") != channel_id:
        payload["last_message_id"] = None
    _sb().table("guild_ark_notifications").upsert(
        payload,
        on_conflict="guild_id",
    ).execute()


def set_ark_notice_last_message(guild_id: str, message_id: str | None) -> None:
    _sb().table("guild_ark_notifications").update(
        {"last_message_id": message_id}
    ).eq("guild_id", guild_id).execute()


def get_ark_notification(guild_id: str) -> dict | None:
    try:
        r = (
            _sb()
            .table("guild_ark_notifications")
            .select("channel_id, last_message_id")
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )
    except Exception:
        r = (
            _sb()
            .table("guild_ark_notifications")
            .select("channel_id")
            .eq("guild_id", guild_id)
            .limit(1)
            .execute()
        )
    if not r.data:
        return None
    row = r.data[0]
    return {
        "channel_id": row["channel_id"],
        "last_message_id": row.get("last_message_id"),
    }


def clear_ark_notification(guild_id: str) -> bool:
    if get_ark_notification(guild_id) is None:
        return False
    _sb().table("guild_ark_notifications").delete().eq("guild_id", guild_id).execute()
    return True


def get_ark_notification_channels() -> list[dict]:
    try:
        r = (
            _sb()
            .table("guild_ark_notifications")
            .select("guild_id, channel_id, last_message_id")
            .execute()
        )
    except Exception:
        r = (
            _sb()
            .table("guild_ark_notifications")
            .select("guild_id, channel_id")
            .execute()
        )
    return [
        {
            "guild_id": row["guild_id"],
            "channel_id": row["channel_id"],
            "last_message_id": row.get("last_message_id"),
        }
        for row in (r.data or [])
    ]


def get_previous_ark_notice() -> str | None:
    _ensure_ark_notice_state_row()
    r = _sb().table("ark_notification_state").select("previous_text").eq("id", 1).limit(1).execute()
    if not r.data:
        return None
    return r.data[0].get("previous_text")


def save_previous_ark_notice(text: str) -> None:
    _ensure_ark_notice_state_row()
    _sb().table("ark_notification_state").update({"previous_text": text}).eq("id", 1).execute()


def get_previous_rate_values() -> dict | None:
    _ensure_rate_state_row()
    r = _sb().table("rate_state").select("previous_rates").eq("id", 1).limit(1).execute()
    if not r.data or r.data[0].get("previous_rates") is None:
        return None
    return r.data[0]["previous_rates"]


def save_previous_rate_values(values: dict) -> None:
    _ensure_rate_state_row()
    _sb().table("rate_state").update({"previous_rates": values}).eq("id", 1).execute()


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


def get_bothunter_configs() -> dict[str, dict]:
    r = (
        _sb()
        .table("bothunter_config")
        .select(
            "guild_id,channel_id,log_channel_id,action,warning_msg_id,"
            "experiments,warning_message,dm_message,log_message,reinvite_code"
        )
        .execute()
    )
    out: dict[str, dict] = {}
    for row in r.data or []:
        value = _bothunter_row_to_dict(row)
        if value is not None:
            out[str(row["guild_id"])] = value
    return out


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


def list_up_notify_watchers_all() -> list[dict]:
    r = (
        _sb()
        .table("server_up_notify")
        .select("server_key,user_id,channel_id,guild_id,query,session_name")
        .order("server_key")
        .execute()
    )
    return [
        {
            "server_key": str(row.get("server_key") or ""),
            "user_id": str(row.get("user_id") or ""),
            "channel_id": str(row.get("channel_id") or ""),
            "guild_id": row.get("guild_id"),
            "query": row.get("query"),
            "session_name": row.get("session_name"),
        }
        for row in (r.data or [])
    ]


def clear_up_notify(server_key: str, channel_id: str | None = None) -> int:
    key = str(server_key).strip()
    if not key:
        return 0
    q = _sb().table("server_up_notify").delete().eq("server_key", key)
    if channel_id:
        q = q.eq("channel_id", str(channel_id))
    r = q.execute()
    return len(r.data or [])
