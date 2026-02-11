"""
Centralized data storage for Sir-5rM8.
All guild and bot state is stored under data/ with a consistent structure.
"""
import json
from pathlib import Path

DATA_DIR = Path("data")
CONFIG_FILE = DATA_DIR / "config.json"
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


def _save_config(config: dict) -> None:
    """Save config to disk."""
    _ensure_data_dir()
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def set_rate_notification(guild_id: str, channel_id: str, role_id: str) -> None:
    """Set rate notification channel and role for a guild."""
    config = _load_config()
    if "guilds" not in config:
        config["guilds"] = {}
    if guild_id not in config["guilds"]:
        config["guilds"][guild_id] = {}

    config["guilds"][guild_id]["rate_notifications"] = {
        "channel_id": channel_id,
        "role_id": role_id,
    }
    _save_config(config)


def get_rate_notification_channels() -> list[dict]:
    """
    Get list of guilds with rate notifications configured.
    Returns list of {server_id, channel_id, role} for compatibility with ratecheck.
    """
    config = _load_config()
    guilds = config.get("guilds", {})
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
