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

DEFAULT_KARMA_HISTORY_LIMIT = 10
DEFAULT_COOLDOWN_HOURS = 24

KARMA_REASON_DISPLAY_MAX = 80
DISCORD_MESSAGE_MAX = 2000
