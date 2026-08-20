"""
JSON file storage (default when no remote database is configured).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import config

DATA_DIR = config.DATA_DIR
CONFIG_FILE = DATA_DIR / "config.json"
RATE_STATE_DIR = DATA_DIR / "rate_state"
RATE_STATE_FILE = RATE_STATE_DIR / "previous_values.json"

CONFIG_VERSION = 1


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RATE_STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict:
    _ensure_data_dir()
    default = {"version": CONFIG_VERSION, "guilds": {}}
    if not CONFIG_FILE.exists():
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return default


def _save_config(data: dict) -> None:
    _ensure_data_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def set_rate_notification(guild_id: str, channel_id: str, role_id: str) -> None:
    data = _load_config()
    if "guilds" not in data:
        data["guilds"] = {}
    if guild_id not in data["guilds"]:
        data["guilds"][guild_id] = {}
    data["guilds"][guild_id]["rate_notifications"] = {
        "channel_id": channel_id,
        "role_id": role_id,
    }
    _save_config(data)


def get_rate_notification(guild_id: str) -> dict | None:
    data = _load_config()
    return data.get("guilds", {}).get(guild_id, {}).get("rate_notifications")


def clear_rate_notification(guild_id: str) -> bool:
    data = _load_config()
    if guild_id not in data.get("guilds", {}):
        return False
    if "rate_notifications" in data["guilds"][guild_id]:
        del data["guilds"][guild_id]["rate_notifications"]
        if not data["guilds"][guild_id]:
            del data["guilds"][guild_id]
        _save_config(data)
        return True
    return False


def get_rate_notification_channels() -> list[dict]:
    data = _load_config()
    result = []
    for server_id, guild_data in data.get("guilds", {}).items():
        rn = guild_data.get("rate_notifications")
        if rn:
            result.append({
                "server_id": server_id,
                "channel_id": rn["channel_id"],
                "role": rn["role_id"],
            })
    return result


def set_ark_notification(guild_id: str, channel_id: str) -> None:
    data = _load_config()
    if "guilds" not in data:
        data["guilds"] = {}
    if guild_id not in data["guilds"]:
        data["guilds"][guild_id] = {}
    data["guilds"][guild_id]["ark_notifications"] = {"channel_id": channel_id}
    _save_config(data)


def get_ark_notification(guild_id: str) -> dict | None:
    data = _load_config()
    return data.get("guilds", {}).get(guild_id, {}).get("ark_notifications")


def clear_ark_notification(guild_id: str) -> bool:
    data = _load_config()
    if guild_id not in data.get("guilds", {}):
        return False
    if "ark_notifications" in data["guilds"][guild_id]:
        del data["guilds"][guild_id]["ark_notifications"]
        if not data["guilds"][guild_id]:
            del data["guilds"][guild_id]
        _save_config(data)
        return True
    return False


def get_ark_notification_channels() -> list[dict]:
    data = _load_config()
    result = []
    for guild_id, guild_data in data.get("guilds", {}).items():
        rn = guild_data.get("ark_notifications")
        if rn and rn.get("channel_id"):
            result.append({"guild_id": guild_id, "channel_id": rn["channel_id"]})
    return result


ARK_NOTICE_STATE_FILE = RATE_STATE_DIR / "ark_notice.json"


def get_previous_ark_notice() -> str | None:
    if not ARK_NOTICE_STATE_FILE.exists():
        return None
    try:
        with open(ARK_NOTICE_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    if not isinstance(payload, dict) or "previous_text" not in payload:
        return None
    return payload.get("previous_text")


def save_previous_ark_notice(text: str) -> None:
    _ensure_data_dir()
    with open(ARK_NOTICE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"previous_text": text}, f, indent=2)


def get_previous_rate_values() -> dict | None:
    if not RATE_STATE_FILE.exists():
        return None
    try:
        with open(RATE_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_previous_rate_values(values: dict) -> None:
    _ensure_data_dir()
    with open(RATE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)


# --- Bothunter (spam trap channel) ---

BOTHUNTER_EVENTS_FILE = DATA_DIR / "bothunter_events.jsonl"


def _bothunter_defaults(guild_id: str) -> dict:
    return {
        "guild_id": str(guild_id),
        "channel_id": None,
        "log_channel_id": None,
        "action": "softban",
        "warning_msg_id": None,
        "experiments": [],
        "warning_message": None,
        "dm_message": None,
        "log_message": None,
        "reinvite_code": None,
    }


def get_bothunter_config(guild_id: str) -> dict | None:
    data = _load_config()
    raw = data.get("guilds", {}).get(str(guild_id), {}).get("bothunter")
    if not raw:
        return None
    cfg = _bothunter_defaults(guild_id)
    cfg.update(raw)
    cfg["guild_id"] = str(guild_id)
    cfg["experiments"] = list(cfg.get("experiments") or [])
    return cfg


def set_bothunter_config(config: dict) -> None:
    guild_id = str(config["guild_id"])
    data = _load_config()
    if "guilds" not in data:
        data["guilds"] = {}
    if guild_id not in data["guilds"]:
        data["guilds"][guild_id] = {}
    stored = _bothunter_defaults(guild_id)
    stored.update({
        "channel_id": config.get("channel_id"),
        "log_channel_id": config.get("log_channel_id"),
        "action": config.get("action") or "softban",
        "warning_msg_id": config.get("warning_msg_id"),
        "experiments": list(config.get("experiments") or []),
        "warning_message": config.get("warning_message"),
        "dm_message": config.get("dm_message"),
        "log_message": config.get("log_message"),
        "reinvite_code": config.get("reinvite_code"),
    })
    data["guilds"][guild_id]["bothunter"] = stored
    _save_config(data)


def clear_bothunter_config(guild_id: str) -> bool:
    data = _load_config()
    guild = data.get("guilds", {}).get(str(guild_id))
    if not guild or "bothunter" not in guild:
        return False
    del guild["bothunter"]
    if not guild:
        del data["guilds"][str(guild_id)]
    _save_config(data)
    return True


def log_bothunter_event(guild_id: str, user_id: str, channel_id: str | None = None) -> None:
    _ensure_data_dir()
    record = {
        "guild_id": str(guild_id),
        "user_id": str(user_id),
        "channel_id": str(channel_id) if channel_id else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with open(BOTHUNTER_EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_bothunter_moderated_count(guild_id: str, channel_id: str | None = None) -> int:
    if not BOTHUNTER_EVENTS_FILE.exists():
        return 0
    count = 0
    try:
        with open(BOTHUNTER_EVENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("guild_id") != str(guild_id):
                    continue
                if channel_id and row.get("channel_id") != str(channel_id):
                    continue
                count += 1
    except IOError:
        return 0
    return count


def get_bothunter_channel_map() -> dict[str, str]:
    """Map channel_id -> guild_id for configured bothunter traps."""
    data = _load_config()
    out: dict[str, str] = {}
    for gid, guild_data in data.get("guilds", {}).items():
        bh = guild_data.get("bothunter") or {}
        channel_id = bh.get("channel_id")
        if channel_id:
            out[str(channel_id)] = str(gid)
    return out


# --- Server player sampling ---

SERVER_WATCHLIST_FILE = DATA_DIR / "server_watchlist.json"
SERVER_SAMPLES_FILE = DATA_DIR / "server_player_samples.jsonl"


def _load_watchlist() -> dict:
    _ensure_data_dir()
    if not SERVER_WATCHLIST_FILE.exists():
        return {}
    try:
        with open(SERVER_WATCHLIST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (IOError, json.JSONDecodeError):
        return {}


def _save_watchlist(data: dict) -> None:
    _ensure_data_dir()
    with open(SERVER_WATCHLIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def watch_server(server_key: str, session_name: str | None = None) -> None:
    key = str(server_key).strip()
    if not key:
        return
    now = datetime.now(timezone.utc).isoformat()
    data = _load_watchlist()
    entry = data.get(key) or {"server_key": key, "created_at": now}
    entry["server_key"] = key
    entry["last_queried"] = now
    if session_name:
        entry["session_name"] = session_name
    data[key] = entry
    if len(data) > config.SERVER_WATCHLIST_MAX:
        ordered = sorted(
            data.items(),
            key=lambda kv: kv[1].get("last_queried") or "",
        )
        for drop_key, _ in ordered[: len(data) - config.SERVER_WATCHLIST_MAX]:
            del data[drop_key]
    _save_watchlist(data)


def record_server_sample(
    server_key: str,
    num_players: int,
    max_players: int,
    *,
    sampled_at: datetime | None = None,
) -> None:
    key = str(server_key).strip()
    if not key:
        return
    ts = sampled_at or datetime.now(timezone.utc)
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    watch_server(key)
    _ensure_data_dir()
    record = {
        "server_key": key,
        "num_players": int(num_players),
        "max_players": int(max_players),
        "sampled_at": ts,
    }
    with open(SERVER_SAMPLES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def get_server_player_history(server_key: str, *, hours: int | None = None) -> list[dict]:
    key = str(server_key).strip()
    if not key or not SERVER_SAMPLES_FILE.exists():
        return []
    from datetime import timedelta

    window = hours if hours is not None else config.SERVER_HISTORY_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=int(window))
    out: list[dict] = []
    try:
        with open(SERVER_SAMPLES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("server_key") != key:
                    continue
                ts_raw = row.get("sampled_at")
                try:
                    ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    continue
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if ts < cutoff:
                    continue
                out.append({
                    "num_players": int(row.get("num_players", 0)),
                    "max_players": int(row.get("max_players", 0)),
                    "sampled_at": ts.isoformat(),
                })
    except IOError:
        return []
    out.sort(key=lambda r: r["sampled_at"])
    return out


def list_watched_server_keys() -> list[str]:
    data = _load_watchlist()
    ordered = sorted(
        data.items(),
        key=lambda kv: kv[1].get("last_queried") or "",
        reverse=True,
    )
    return [str(k) for k, _ in ordered]


def prune_server_samples(*, retention_days: int | None = None) -> int:
    if not SERVER_SAMPLES_FILE.exists():
        return 0
    from datetime import timedelta

    days = retention_days if retention_days is not None else config.SERVER_SAMPLE_RETENTION_DAYS
    cutoff = datetime.now(timezone.utc) - timedelta(days=int(days))
    kept: list[str] = []
    removed = 0
    try:
        with open(SERVER_SAMPLES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                    ts = datetime.fromisoformat(str(row.get("sampled_at")).replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        removed += 1
                        continue
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
                kept.append(raw)
        with open(SERVER_SAMPLES_FILE, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")
    except IOError:
        return 0
    return removed


UP_NOTIFY_FILE = DATA_DIR / "server_up_notify.json"


def _load_up_notify() -> list[dict]:
    _ensure_data_dir()
    if not UP_NOTIFY_FILE.exists():
        return []
    try:
        with open(UP_NOTIFY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (IOError, json.JSONDecodeError):
        return []


def _save_up_notify(rows: list[dict]) -> None:
    _ensure_data_dir()
    with open(UP_NOTIFY_FILE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)


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
    rows = _load_up_notify()
    for row in rows:
        if (
            str(row.get("server_key")) == key
            and str(row.get("user_id")) == uid
            and str(row.get("channel_id")) == cid
        ):
            return False
    rows.append({
        "server_key": key,
        "user_id": uid,
        "channel_id": cid,
        "guild_id": str(guild_id) if guild_id else None,
        "query": query,
        "session_name": session_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    _save_up_notify(rows)
    return True


def list_up_notify_keys() -> list[str]:
    keys = sorted({str(row.get("server_key") or "") for row in _load_up_notify() if row.get("server_key")})
    return keys


def list_up_notify_watchers(server_key: str) -> list[dict]:
    key = str(server_key).strip()
    if not key:
        return []
    out: list[dict] = []
    for row in _load_up_notify():
        if str(row.get("server_key")) == key:
            out.append({
                "server_key": key,
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
    rows = _load_up_notify()
    kept: list[dict] = []
    removed = 0
    cid = str(channel_id) if channel_id else None
    for row in rows:
        if str(row.get("server_key")) != key:
            kept.append(row)
            continue
        if cid is not None and str(row.get("channel_id")) != cid:
            kept.append(row)
            continue
        removed += 1
    if removed:
        _save_up_notify(kept)
    return removed
