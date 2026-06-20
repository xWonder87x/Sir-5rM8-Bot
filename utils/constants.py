"""
Shared constants for Sir-5rM8.
"""
from __future__ import annotations

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
