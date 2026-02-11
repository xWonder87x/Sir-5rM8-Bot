import re
import time
import requests
from utils import storage

server_url = 'https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json'
rate_url = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"

# Rate keys we care about (order matches embed display)
RATE_KEYS = [
    "XPMultiplier",
    "HarvestAmountMultiplier",
    "TamingSpeedMultiplier",
    "MatingIntervalMultiplier",
    "EggHatchSpeedMultiplier",
    "BabyMatureSpeedMultiplier",
    "BabyImprintAmountMultiplier",
    "BabyCuddleIntervalMultiplier",
]

HTTP_RETRIES = 3
HTTP_RETRY_DELAY = 2


def _parse_rate_config(text: str) -> dict:
    """Parse dynamicconfig.ini into a dict of key -> value."""
    result = {}
    for line in text.split('\n'):
        match = re.match(r"^\s*([\w.]+)\s*=\s*([\w.-]+)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _extract_relevant_rates(parsed: dict) -> dict:
    """Extract only the rate keys we care about."""
    return {k: parsed.get(k, "?") for k in RATE_KEYS}


def _rates_changed(previous: dict, current: dict) -> bool:
    """Compare only relevant rate values."""
    for key in RATE_KEYS:
        if previous.get(key) != current.get(key):
            return True
    return False


def find_server(query: str) -> dict | None:
    """
    Search for an ASA server by name or number.
    Returns server dict if found, None otherwise.
    """
    for attempt in range(HTTP_RETRIES):
        try:
            resp = requests.get(server_url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            query_lower = query.lower().strip()
            for server in data:
                if 'SessionName' in server and query_lower in server['SessionName'].lower():
                    return server
            return None
        except (requests.RequestException, requests.HTTPError) as e:
            if attempt < HTTP_RETRIES - 1:
                time.sleep(HTTP_RETRY_DELAY)
            else:
                print(f"find_server failed: {e}")
                return None


def fetch_current_rates() -> dict | None:
    """Fetch and parse current ASA rates. Returns dict of rate values or None on failure."""
    for attempt in range(HTTP_RETRIES):
        try:
            resp = requests.get(rate_url, timeout=10)
            resp.raise_for_status()
            parsed = _parse_rate_config(resp.text)
            return _extract_relevant_rates(parsed)
        except (requests.RequestException, requests.HTTPError) as e:
            if attempt < HTTP_RETRIES - 1:
                time.sleep(HTTP_RETRY_DELAY)
            else:
                print(f"Fetch rates failed: {e}")
                return None


def add_server_channel(server_id: str, channel_id: str, role_id: str) -> None:
    """Register a guild's rate notification channel and role."""
    storage.set_rate_notification(server_id, channel_id, role_id)


def loop() -> tuple[list | None, dict | None, dict | None, int]:
    """
    Check if ASA rates have changed.
    Returns (server_list, current_rates, previous_rates, flag).
    flag=0 means rates changed (send notifications), flag=1 means no change.
    """
    last_error = None
    for attempt in range(HTTP_RETRIES):
        try:
            resp = requests.get(rate_url, timeout=10)
            resp.raise_for_status()
            break
        except (requests.RequestException, requests.HTTPError) as e:
            last_error = e
            if attempt < HTTP_RETRIES - 1:
                time.sleep(HTTP_RETRY_DELAY)
            else:
                print(f"Rate check failed after {HTTP_RETRIES} attempts: {e}")
                return None, None, None, 1

    current_parsed = _parse_rate_config(resp.text)
    current_rates = _extract_relevant_rates(current_parsed)
    previous = storage.get_previous_rate_values()

    if previous is None:
        storage.save_previous_rate_values(current_rates)
        return None, None, None, 1

    if _rates_changed(previous, current_rates):
        storage.save_previous_rate_values(current_rates)
        server_list = storage.get_rate_notification_channels()
        return server_list, current_rates, previous, 0

    return None, None, None, 1
