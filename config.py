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

# ASA API
RATE_URL = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"
SERVER_LIST_URL = "https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json"

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

# Legacy local player-sample helpers (unused by /serverstatus; kept for db API compat)
SERVER_WATCHLIST_MAX = int(os.environ.get("SERVER_WATCHLIST_MAX", "200"))
SERVER_HISTORY_HOURS = int(os.environ.get("SERVER_HISTORY_HOURS", "24"))
SERVER_SAMPLE_RETENTION_DAYS = int(os.environ.get("SERVER_SAMPLE_RETENTION_DAYS", "7"))

DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24

KARMA_REASON_DISPLAY_MAX = 80
DISCORD_MESSAGE_MAX = 2000

# DM this user once when the bot process comes online (restart/redeploy). None = disabled.
# Override with RESTART_NOTIFY_USER_ID in the environment if needed.
_restart_notify_raw = os.environ.get("RESTART_NOTIFY_USER_ID", "464386520124620800")
RESTART_NOTIFY_USER_ID: int | None = (
    int(_restart_notify_raw) if _restart_notify_raw.strip().isdigit() else None
)
