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


def server_key_from_server(server: dict) -> str:
    """Stable key for watchlist / samples: prefer numeric id, else session name."""
    session_name = str(server.get("SessionName") or "").strip()
    number = _server_number(session_name) if session_name else None
    if number:
        return number
    if session_name:
        return session_name
    ip = str(server.get("IP") or "").strip()
    return ip or "unknown"


_NOTIFY_KEY_RE = re.compile(r"[^A-Za-z0-9._-]+")
_TRAILING_NUMBER_RE = re.compile(r"(\d{3,5})\s*$")


def notify_key(value: str) -> str:
    """Discord custom_id-safe key (max 80 chars)."""
    cleaned = _NOTIFY_KEY_RE.sub("_", str(value).strip()).strip("._-")[:80]
    return cleaned or "unknown"


def notify_key_from_server(server: dict) -> str:
    return notify_key(server_key_from_server(server))


def query_server_number(query: str) -> str | None:
    q = (query or "").strip()
    if not q:
        return None
    if q.isdigit():
        return q
    named = _server_number(q)
    if named:
        return named
    match = _TRAILING_NUMBER_RE.search(q)
    return match.group(1) if match else None


def query_server_key(query: str) -> str:
    number = query_server_number(query)
    if number:
        return number
    return notify_key(query)


def _score_server(server: dict, query: str) -> int:
    query_stripped = query.strip()
    query_lower = query_stripped.lower()
    session_name = server.get("SessionName", "")
    short_name = str(server.get("Name") or "").strip()
    name_lower = session_name.lower()
    name_upper = server.get("SessionNameUpper", session_name.upper())
    session_id = str(server.get("SessionID") or "").strip()
    ip = str(server.get("IP") or "").strip()
    port = str(server.get("Port") or "").strip()

    if not session_name and not short_name and not session_id and not ip:
        return 0

    if session_id and query_stripped.lower() == session_id.lower():
        return 500
    if short_name and query_lower == short_name.lower():
        return 400
    if ip and (query_stripped == ip or (port and query_stripped == f"{ip}:{port}")):
        return 350

    if query_stripped.isdigit():
        server_num = _server_number(session_name) or query_server_number(short_name or session_name)
        if server_num == query_stripped:
            return 300
        if query_stripped in name_lower or query_stripped in short_name.lower():
            return 100

    if query_lower == name_lower:
        return 250
    if query_stripped.upper() == name_upper:
        return 240
    # Substring is last-resort only (many ASA names overlap).
    if query_lower in name_lower or (short_name and query_lower in short_name.lower()):
        return 50
    if query_stripped.upper() in name_upper:
        return 40

    return 0


def fetch_official_servers() -> list[dict] | None:
    """Official ASA list from the shared cache. None if the CDN request failed and no live snapshot exists."""
    from functions.asa_cache import get_snapshot

    snap = get_snapshot()
    if snap.fetch_ok:
        return snap.as_raw_list()
    return None


def match_server_in_list(servers: list[dict], query: str) -> dict | None:
    query = query.strip()
    if not query:
        return None
    best: dict | None = None
    best_score = 0
    for server in servers:
        try:
            score = _score_server(server, query)
        except Exception:
            continue
        if score > best_score:
            best_score = score
            best = server
    # Require a real identifier match; weak substring-only hits need score >= 50
    # but digit-in-name (100) and exact matches rank higher.
    return best if best_score > 0 else None


def match_server_key_in_list(servers: list[dict], server_key: str) -> dict | None:
    key = notify_key(server_key)
    if key == "unknown" and not str(server_key).strip():
        return None
    for server in servers:
        if notify_key_from_server(server) == key:
            return server
    return match_server_in_list(servers, str(server_key).strip())


def find_server(query: str) -> ServerLookupResult:
    """Search for an ASA server by name or number."""
    servers = fetch_official_servers()
    if servers is None:
        return ServerLookupResult(error="fetch_failed")
    query = query.strip()
    if not query:
        return ServerLookupResult(error="not_found")
    best = match_server_in_list(servers, query)
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
