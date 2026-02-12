"""
Centralized data storage for Sir-5rM8.
All guild and bot state is stored under data/ with a consistent structure.
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

# Schema version for future migrations
CONFIG_VERSION = 1


def _ensure_data_dir():
    """Ensure data directory and subdirs exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RATE_STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_config() -> dict:
    """Load config or return default structure."""
    _ensure_data_dir()
    default = {"version": CONFIG_VERSION, "guilds": {}}
    if not CONFIG_FILE.exists():
        return default
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, IOError):
        return default


def _save_config(data: dict) -> None:
    """Save config to disk (atomic: temp file + rename)."""
    _ensure_data_dir()
    tmp = CONFIG_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CONFIG_FILE)


def set_rate_notification(guild_id: str, channel_id: str, role_id: str) -> None:
    """Set rate notification channel and role for a guild."""
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
    """Get rate notification config for a guild. Returns {channel_id, role_id} or None."""
    data = _load_config()
    rn = data.get("guilds", {}).get(guild_id, {}).get("rate_notifications")
    return rn


def clear_rate_notification(guild_id: str) -> bool:
    """Remove rate notification config for a guild. Returns True if it existed."""
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
    """
    Get list of guilds with rate notifications configured.
    Returns list of {server_id, channel_id, role} for compatibility with ratecheck.
    """
    data = _load_config()
    guilds = data.get("guilds", {})
    result = []
    for server_id, guild_data in guilds.items():
        rn = guild_data.get("rate_notifications")
        if rn:
            result.append({
                "server_id": server_id,
                "channel_id": rn["channel_id"],
                "role": rn["role_id"],
            })
    return result


def get_previous_rate_values() -> dict | None:
    """Get previous parsed rate values, or None if not yet stored."""
    if not RATE_STATE_FILE.exists():
        return None
    try:
        with open(RATE_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_previous_rate_values(values: dict) -> None:
    """Save parsed rate values for next comparison."""
    _ensure_data_dir()
    with open(RATE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2)


# --- Karma (global, per-person, shared across all guilds) ---

DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24
KARMA_HISTORY_TAIL_BYTES = 512 * 1024  # Read last 512KB for history lookup


def _get_karma_config(data: dict) -> dict:
    """Get karma config with defaults for cooldown_hours and history_limit."""
    karma = _get_karma(data)
    return {
        "cooldown_hours": karma.get("cooldown_hours", DEFAULT_COOLDOWN_HOURS),
        "history_limit": karma.get("history_limit", DEFAULT_KARMA_HISTORY_LIMIT),
    }


def get_karma_settings() -> dict:
    """Get karma settings (cooldown_hours, history_limit) from config."""
    return _get_karma_config(_load_config())


def _get_karma(data: dict) -> dict:
    """Get or create global karma section (balances + cooldowns only; history is in JSONL)."""
    if "karma" not in data:
        data["karma"] = {"balances": {}, "cooldowns": {}}
    karma = data["karma"]
    # Migrate old cooldown format (giver_id only) to new (giver_id:receiver_id)
    cooldowns = karma.get("cooldowns", {})
    old_keys = [k for k in cooldowns if ":" not in k]
    for k in old_keys:
        del cooldowns[k]
    return karma


def _append_karma_history(user_id: str, entry: dict) -> None:
    """Append one history entry to karma_history.jsonl."""
    _ensure_data_dir()
    record = {"user_id": user_id, **entry}
    with open(KARMA_HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _migrate_history_to_jsonl() -> None:
    """One-time migration: move history from config.json to karma_history.jsonl."""
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
    """Get karma balance for a user (global)."""
    data = _load_config()
    karma = _get_karma(data)
    return karma["balances"].get(user_id, 0)


def _cooldown_key(giver_id: str, receiver_id: str) -> str:
    """Key for per-pair cooldown (giver -> receiver)."""
    return f"{giver_id}:{receiver_id}"


def karma_get_cooldown(giver_id: str, receiver_id: str) -> datetime | None:
    """Get last karma-given timestamp for this giver->receiver pair. Returns None if not on cooldown."""
    data = _load_config()
    karma = _get_karma(data)
    key = _cooldown_key(giver_id, receiver_id)
    ts = karma["cooldowns"].get(key)
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
    """Add 1 karma from giver to receiver. Returns new receiver balance."""
    data = _load_config()
    karma = _get_karma(data)
    karma["balances"][receiver_id] = karma["balances"].get(receiver_id, 0) + 1
    now = datetime.now(timezone.utc).isoformat()
    karma["cooldowns"][_cooldown_key(giver_id, receiver_id)] = now
    _save_config(data)
    entry = {
        "timestamp": now,
        "action": "add",
        "amount": 1,
        "by": giver_name,
        "giver_id": giver_id,
        "reason": reason,
    }
    _append_karma_history(receiver_id, entry)
    return karma["balances"][receiver_id]


def karma_take(target_id: str, admin_id: str, admin_name: str) -> int | None:
    """Remove 1 karma from target. Returns new balance or None if already 0."""
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
    """Read last N bytes from karma_history.jsonl, return lines (newest first)."""
    if not KARMA_HISTORY_FILE.exists():
        return []
    try:
        with open(KARMA_HISTORY_FILE, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            start = max(0, size - KARMA_HISTORY_TAIL_BYTES)
            f.seek(start)
            if start > 0:
                f.readline()  # skip partial line
            lines = [l.decode("utf-8", errors="replace").strip() for l in f.readlines()]
    except IOError:
        return []
    return list(reversed(lines))


def karma_get_history(user_id: str) -> list[dict]:
    """Get karma history for a user (last N entries). Reads from end of file for efficiency."""
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
    """Get recent take-karma (remove) events for admin audit."""
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
