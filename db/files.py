"""
JSON file storage (default when Supabase env vars are not set).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import config

DATA_DIR = config.DATA_DIR
CONFIG_FILE = DATA_DIR / "config.json"
KARMA_HISTORY_FILE = DATA_DIR / "karma_history.jsonl"
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


KARMA_HISTORY_TAIL_BYTES = 512 * 1024


def _get_karma_config(data: dict) -> dict:
    karma = _get_karma(data)
    return {
        "cooldown_hours": karma.get("cooldown_hours", config.DEFAULT_COOLDOWN_HOURS),
        "history_limit": karma.get("history_limit", config.DEFAULT_KARMA_HISTORY_LIMIT),
    }


def get_karma_settings() -> dict:
    return _get_karma_config(_load_config())


def _get_karma(data: dict) -> dict:
    if "karma" not in data:
        data["karma"] = {"balances": {}, "cooldowns": {}}
    karma = data["karma"]
    cooldowns = karma.get("cooldowns", {})
    for k in [k for k in cooldowns if ":" not in k]:
        del cooldowns[k]
    return karma


def _append_karma_history(user_id: str, entry: dict) -> None:
    _ensure_data_dir()
    record = {"user_id": user_id, **entry}
    with open(KARMA_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _migrate_history_to_jsonl() -> None:
    if KARMA_HISTORY_FILE.exists():
        return
    data = _load_config()
    if "karma" not in data or "history" not in data["karma"]:
        return
    for user_id, entries in data["karma"]["history"].items():
        for e in entries:
            _append_karma_history(user_id, e)
    del data["karma"]["history"]
    _save_config(data)


def karma_get_balance(user_id: str) -> int:
    data = _load_config()
    karma = _get_karma(data)
    return karma["balances"].get(user_id, 0)


def _cooldown_key(giver_id: str, receiver_id: str) -> str:
    return f"{giver_id}:{receiver_id}"


def karma_get_cooldown(giver_id: str, receiver_id: str) -> datetime | None:
    data = _load_config()
    karma = _get_karma(data)
    ts = karma["cooldowns"].get(_cooldown_key(giver_id, receiver_id))
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def karma_add(giver_id: str, receiver_id: str, giver_name: str, reason: str) -> int:
    data = _load_config()
    karma = _get_karma(data)
    karma["balances"][receiver_id] = karma["balances"].get(receiver_id, 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    karma["cooldowns"][_cooldown_key(giver_id, receiver_id)] = now
    _save_config(data)
    _append_karma_history(receiver_id, {
        "timestamp": now,
        "action": "add",
        "amount": 1,
        "by": giver_name,
        "giver_id": giver_id,
        "reason": reason,
    })
    return karma["balances"][receiver_id]


def karma_take(target_id: str, admin_id: str, admin_name: str) -> int | None:
    data = _load_config()
    karma = _get_karma(data)
    balance = karma["balances"].get(target_id, 0)
    if balance <= 0:
        return None
    karma["balances"][target_id] = balance - 1
    _save_config(data)
    _append_karma_history(target_id, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": "remove",
        "amount": 1,
        "by": admin_name,
        "admin_id": admin_id,
    })
    return karma["balances"][target_id]


def _read_history_tail() -> list[str]:
    if not KARMA_HISTORY_FILE.exists():
        return []
    try:
        with open(KARMA_HISTORY_FILE, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - KARMA_HISTORY_TAIL_BYTES)
            f.seek(start)
            if start > 0:
                f.readline()
            lines = [l.decode("utf-8", errors="replace").strip() for l in f.readlines()]
    except IOError:
        return []
    return list(reversed(lines))


def karma_get_history(user_id: str) -> list[dict]:
    _migrate_history_to_jsonl()
    limit = _get_karma_config(_load_config())["history_limit"]
    entries = []
    for line in _read_history_tail():
        if not line:
            continue
        try:
            record = json.loads(line)
            if record.get("user_id") == user_id:
                entries.append({k: v for k, v in record.items() if k != "user_id"})
                if len(entries) >= limit:
                    break
        except json.JSONDecodeError:
            continue
    return entries


def karma_get_audit(limit: int = 20) -> list[dict]:
    _migrate_history_to_jsonl()
    audit = []
    for line in _read_history_tail():
        if not line:
            continue
        try:
            record = json.loads(line)
            if record.get("action") == "remove":
                audit.append(record)
                if len(audit) >= limit:
                    break
        except json.JSONDecodeError:
            continue
    return audit


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
