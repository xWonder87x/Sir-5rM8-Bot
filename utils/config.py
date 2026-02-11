import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bot
TOKEN = os.getenv("TOKEN")

# ASA API URLs
RATE_URL = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"
SERVER_LIST_URL = "https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json"

# Assets
THUMBNAIL_URL = "https://ark.wiki.gg/images/thumb/0/0a/ASA_Logo_transparent.png/198px-ASA_Logo_transparent.png"

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
