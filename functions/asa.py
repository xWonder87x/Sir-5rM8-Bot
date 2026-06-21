"""
ASA (ARK: Survival Ascended) API client.
Handles fetching and parsing rates and server list.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger(__name__)

_HTTP_RETRIES = config.HTTP_RETRIES
_HTTP_RETRY_DELAY = config.HTTP_RETRY_DELAY

_SERVER_NUMBER_RE = re.compile(r"(\d+)\s*-\s*\(")


@dataclass(frozen=True)
class ServerLookupResult:
    server: dict | None = None
    error: str | None = None  # "fetch_failed" | "not_found"

    @property
    def ok(self) -> bool:
        return self.server is not None


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
    return {k: parsed.get(k, "?") for k in config.RATE_KEYS}


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
                logger.error("Fetch failed (%s): %s", url, e)
                return None
    return None


def _server_number(session_name: str) -> str | None:
    """Extract trailing server number from names like 'EU-PVE-TheIsland5313 - (v88.23)'."""
    match = _SERVER_NUMBER_RE.search(session_name)
    return match.group(1) if match else None


def _score_server(server: dict, query: str) -> int:
    query_stripped = query.strip()
    query_lower = query_stripped.lower()
    session_name = server.get("SessionName", "")
    name_lower = session_name.lower()
    name_upper = server.get("SessionNameUpper", session_name.upper())

    if not session_name:
        return 0

    if query_stripped.isdigit():
        server_num = _server_number(session_name)
        if server_num == query_stripped:
            return 300
        if query_stripped in name_lower:
            return 100

    if query_lower == name_lower:
        return 250
    if query_stripped.upper() == name_upper:
        return 240
    if query_lower in name_lower:
        return 50
    if query_stripped.upper() in name_upper:
        return 40

    return 0


def find_server(query: str) -> ServerLookupResult:
    """Search for an ASA server by name or number."""
    resp = _fetch_with_retry(config.SERVER_LIST_URL)
    if not resp:
        return ServerLookupResult(error="fetch_failed")

    query = query.strip()
    if not query:
        return ServerLookupResult(error="not_found")

    best: dict | None = None
    best_score = 0
    for server in resp.json():
        score = _score_server(server, query)
        if score > best_score:
            best_score = score
            best = server

    if best is None:
        return ServerLookupResult(error="not_found")
    return ServerLookupResult(server=best)


def fetch_current_rates() -> dict | None:
    """Fetch and parse current ASA rates. Returns dict of rate values or None."""
    resp = _fetch_with_retry(config.RATE_URL)
    if not resp:
        return None
    parsed = _parse_rate_config(resp.text)
    return _extract_relevant_rates(parsed)
