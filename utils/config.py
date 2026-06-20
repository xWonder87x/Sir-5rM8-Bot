"""Bot configuration loaded from environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Bot
TOKEN = os.getenv("TOKEN")

# Supabase (optional — if both set, storage uses PostgreSQL instead of local JSON)
def _normalize_supabase_url(url: str) -> str:
    url = url.strip().strip('"').strip("'").rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


_raw_supabase_url = (os.getenv("SUPABASE_URL") or "").strip()
SUPABASE_SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip() or None
SUPABASE_URL = _normalize_supabase_url(_raw_supabase_url) if _raw_supabase_url else None

USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)
STORAGE_BACKEND = "supabase" if USE_SUPABASE else "json_files"

# ASA API URLs
RATE_URL = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"
SERVER_LIST_URL = "https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json"

# Assets
THUMBNAIL_URL = "https://ark.wiki.gg/images/thumb/0/0a/ASA_Logo_transparent.png/198px-ASA_Logo_transparent.png"

# Paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
