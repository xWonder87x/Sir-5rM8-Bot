"""Bot configuration: IDs, tunables, and env reads — no secrets hard-coded."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", PROJECT_ROOT / "data"))

TOKEN = os.getenv("TOKEN")

_slash_sync_raw = os.environ.get("SLASH_SYNC_GUILD_IDS", "")
SLASH_SYNC_GUILD_IDS: list[int] = [
    int(x.strip()) for x in _slash_sync_raw.split(",") if x.strip().isdigit()
]

# ASA API (Studio Wildcard CDN)
RATE_URL = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"
SERVER_LIST_URL = "https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json"
NETWORK_STATUS_URL = os.environ.get(
    "NETWORK_STATUS_URL",
    "https://cdn2.arkdedicated.com/asa/officialserverstatus.ini",
).strip()
NOTIFICATION_URL = os.environ.get(
    "NOTIFICATION_URL",
    "https://cdn2.arkdedicated.com/asa/notification.html",
).strip()
ASA_POLL_SECONDS = int(os.environ.get("ASA_POLL_SECONDS", "60"))
ASA_CACHE_TTL_SECONDS = int(os.environ.get("ASA_CACHE_TTL_SECONDS", "60"))
ASA_OFFLINE_MISS_THRESHOLD = int(os.environ.get("ASA_OFFLINE_MISS_THRESHOLD", "2"))
ASA_STALE_SECONDS = int(os.environ.get("ASA_STALE_SECONDS", "300"))
ASA_BM_FALLBACK = os.environ.get("ASA_BM_FALLBACK", "1").strip().lower() not in ("0", "false", "no")
ASA_BM_COMPARE = os.environ.get("ASA_BM_COMPARE", "1").strip().lower() not in ("0", "false", "no")

THUMBNAIL_URL = (
    "https://ark.wiki.gg/images/thumb/0/0a/ASA_Logo_transparent.png/198px-ASA_Logo_transparent.png"
)

# Rate display: (emoji, label, config_key)
RATE_DISPLAY = [
    ("✨", "EXP", "XPMultiplier"),
    ("🌴", "Harvesting", "HarvestAmountMultiplier"),
    ("🦖", "Taming", "TamingSpeedMultiplier"),
    ("💞", "Mating Interval", "MatingIntervalMultiplier"),
    ("🐣", "Egg Hatch", "EggHatchSpeedMultiplier"),
    ("🐤", "Baby Mature", "BabyMatureSpeedMultiplier"),
    ("🤗", "Imprint", "BabyImprintAmountMultiplier"),
    ("🤗", "Cuddle Interval", "BabyCuddleIntervalMultiplier"),
]

RATE_KEYS = [key for _, _, key in RATE_DISPLAY]

HTTP_RETRIES = 3
HTTP_RETRY_DELAY = 2

# /serverstatus charts (BattleMetrics uptime)
BATTLEMETRICS_TOKEN = os.environ.get("BATTLEMETRICS_TOKEN", "").strip()
BM_UPTIME_HISTORY_DAYS = int(os.environ.get("BM_UPTIME_HISTORY_DAYS", "90"))
BM_UPTIME_RESOLUTION_MINUTES = int(os.environ.get("BM_UPTIME_RESOLUTION_MINUTES", "60"))
SERVER_UP_CHECK_MINUTES = int(os.environ.get("SERVER_UP_CHECK_MINUTES", "1"))
OUTAGE_REPORT_URL = os.environ.get(
    "OUTAGE_REPORT_URL",
    "https://docs.google.com/forms/d/e/1FAIpQLSd8Xn6z_RP7fxGgH_86VZAKDzqmbDboanrC51GSpr_1v9_PLA/viewform",
).strip()

# Legacy local player-sample helpers (unused by /serverstatus; kept for db API compat)
SERVER_WATCHLIST_MAX = int(os.environ.get("SERVER_WATCHLIST_MAX", "200"))
SERVER_HISTORY_HOURS = int(os.environ.get("SERVER_HISTORY_HOURS", "24"))
SERVER_SAMPLE_RETENTION_DAYS = int(os.environ.get("SERVER_SAMPLE_RETENTION_DAYS", "7"))

DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24

KARMA_REASON_DISPLAY_MAX = 80
DISCORD_MESSAGE_MAX = 2000


def _optional_snowflake(name: str, default: str = "") -> int | None:
    raw = (os.environ.get(name, default) or "").strip()
    return int(raw) if raw.isdigit() else None


# Permanent guild-list embed (replaces /servers). Env GUILD_LIST_CHANNEL_ID overrides.
CHANNELS = {
    "guild_list": None,
}
GUILD_LIST_CHANNEL_ID: int | None = (
    _optional_snowflake("GUILD_LIST_CHANNEL_ID") or CHANNELS["guild_list"]
)

# Ping this user in GUILD_LIST_CHANNEL_ID on restart/redeploy and guild join. None = disabled.
# Override with RESTART_NOTIFY_USER_ID in the environment if needed.
_restart_notify_raw = os.environ.get("RESTART_NOTIFY_USER_ID", "464386520124620800")
RESTART_NOTIFY_USER_ID: int | None = (
    int(_restart_notify_raw) if _restart_notify_raw.strip().isdigit() else None
)
