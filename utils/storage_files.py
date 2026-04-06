"""
JSON file storage (default when Supabase env vars are not set).
"""
import json
import os
from datetime import datetime, timezone

from utils import config

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


DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24
KARMA_HISTORY_TAIL_BYTES = 512 * 1024


def _get_karma_config(data: dict) -> dict:
    karma = _get_karma(data)
    return {
        "cooldown_hours": karma.get("cooldown_hours", DEFAULT_COOLDOWN_HOURS),
        "history_limit": karma.get("history_limit", DEFAULT_KARMA_HISTORY_LIMIT),
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
