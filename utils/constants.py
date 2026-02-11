"""
Shared constants for Sir-5rM8.
"""

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
