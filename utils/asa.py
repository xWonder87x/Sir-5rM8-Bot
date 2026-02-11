"""
ASA (ARK: Survival Ascended) API client.
Handles fetching and parsing rates and server list.
"""
import re
import time

import requests

from utils import config, constants

_HTTP_RETRIES = constants.HTTP_RETRIES
_HTTP_RETRY_DELAY = constants.HTTP_RETRY_DELAY


def _parse_rate_config(text: str) -> dict:
    """Parse dynamicconfig.ini into key -> value."""
    result = {}
    for line in text.split("\n"):
        match = re.match(r"^\s*([\w.]+)\s*=\s*([\w.-]+)\s*$", line)
        if match:
            result[match.group(1)] = match.group(2)
    return result


def _extract_relevant_rates(parsed: dict) -> dict:
    """Extract only the rate keys we care about."""
    return {k: parsed.get(k, "?") for k in constants.RATE_KEYS}


def _fetch_with_retry(url: str) -> requests.Response | None:
    """Fetch URL with retries. Returns Response or None on failure."""
    for attempt in range(_HTTP_RETRIES):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp
        except (requests.RequestException, requests.HTTPError) as e:
            if attempt < _HTTP_RETRIES - 1:
                time.sleep(_HTTP_RETRY_DELAY)
            else:
                print(f"Fetch failed ({url}): {e}")
                return None


def find_server(query: str) -> dict | None:
    """Search for an ASA server by name or number. Returns server dict or None."""
    resp = _fetch_with_retry(config.SERVER_LIST_URL)
    if not resp:
        return None
    data = resp.json()
    query_lower = query.lower().strip()
    for server in data:
        if "SessionName" in server and query_lower in server["SessionName"].lower():
            return server
    return None


def fetch_current_rates() -> dict | None:
    """Fetch and parse current ASA rates. Returns dict of rate values or None."""
    resp = _fetch_with_retry(config.RATE_URL)
    if not resp:
        return None
    parsed = _parse_rate_config(resp.text)
    return _extract_relevant_rates(parsed)
