"""Official Studio Wildcard ASA CDN client (list, network status, announcements)."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

import requests

import config
from functions.asa_models import AsaAnnouncement, AsaServer, AsaSnapshot, NetworkStatus

logger = logging.getLogger(__name__)

_HTTP_RETRIES = config.HTTP_RETRIES
_HTTP_RETRY_DELAY = config.HTTP_RETRY_DELAY

_NETWORK_STATUS_RE = re.compile(
    r"Network Status:\s*(?:<RichColor[^>]*>)?\s*(Online|Offline)\b"
    r"(?:\s*\(v?([0-9.]+)\))?",
    re.IGNORECASE,
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_EMPTY_NOTICE = frozenset({"", ".", "..", "...", "none", "n/a"})
_ANNOUNCEMENT_MAX = 4000


def fetch_url(url: str, *, timeout: int = 15) -> requests.Response | None:
    """GET with retries. None on HTTP/network failure (not on 200 empty body)."""
    last_exc: Exception | None = None
    for attempt in range(_HTTP_RETRIES):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except (requests.RequestException, requests.HTTPError) as exc:
            last_exc = exc
            if attempt < _HTTP_RETRIES - 1:
                time.sleep(_HTTP_RETRY_DELAY)
    logger.warning("ASA CDN fetch failed (%s): %s", url, last_exc)
    return None


def _safe_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def parse_last_updated(value: Any, *, now: datetime | None = None) -> tuple[datetime | None, float | None]:
    """Official list uses unix milliseconds (e.g. 1787048249444). Also accept seconds."""
    now = now or datetime.now(timezone.utc)
    try:
        raw = int(value)
    except (TypeError, ValueError):
        return None, None
    if raw <= 0:
        return None, None
    if raw >= 10**12:
        ts = datetime.fromtimestamp(raw / 1000.0, tz=timezone.utc)
    elif raw >= 10**9:
        ts = datetime.fromtimestamp(raw, tz=timezone.utc)
    else:
        return None, None
    age = max(0.0, (now - ts).total_seconds())
    return ts, age


def parse_asa_server(row: Any, *, now: datetime | None = None) -> AsaServer | None:
    """Map one official-list object. Returns None for malformed rows."""
    from functions.asa import notify_key_from_server, query_server_number

    if not isinstance(row, dict):
        return None
    session_name = _safe_str(row.get("SessionName")) or _safe_str(row.get("Name"))
    if not session_name:
        return None
    name = _safe_str(row.get("Name")) or session_name.split(" - (")[0]
    session_id = _safe_str(row.get("SessionID"))
    ip = _safe_str(row.get("IP"))
    port = _safe_int(row.get("Port"))
    map_name = _safe_str(row.get("MapName")).replace("_WP", "") or "—"
    num_players = _safe_int(row.get("NumPlayers")) or 0
    max_players = _safe_int(row.get("MaxPlayers")) or 70
    ping = _safe_int(row.get("ServerPing"))
    build_id = _safe_int(row.get("BuildId"))
    minor = _safe_int(row.get("MinorBuildId"))
    version = None
    if build_id is not None and minor is not None:
        version = f"v{build_id}.{minor}"
    elif build_id is not None:
        version = f"v{build_id}"
    last_updated, age = parse_last_updated(row.get("LastUpdated"), now=now)
    official_raw = row.get("IsOfficial")
    is_official = str(official_raw).strip() in ("1", "true", "True")
    pve_raw = row.get("SessionIsPve")
    session_is_pve = None
    if pve_raw is not None:
        session_is_pve = str(pve_raw).strip() in ("1", "true", "True")
    key_src = {
        "SessionName": session_name,
        "Name": name,
        "IP": ip,
        "SessionID": session_id,
    }
    server_key = notify_key_from_server(key_src)
    if server_key == "unknown":
        number = query_server_number(name) or query_server_number(session_name)
        server_key = number or session_id[:80] or ip or "unknown"
    return AsaServer(
        session_id=session_id,
        name=name,
        session_name=session_name,
        ip=ip or "—",
        port=port,
        map_name=map_name,
        num_players=num_players,
        max_players=max_players,
        ping=ping,
        build_id=build_id,
        minor_build_id=minor,
        version=version,
        platform=_safe_str(row.get("PlatformType")) or "—",
        cluster_id=_safe_str(row.get("ClusterId")),
        day_time=_safe_str(row.get("DayTime")) or "—",
        last_updated=last_updated,
        last_updated_age_seconds=age,
        is_official=is_official,
        session_is_pve=session_is_pve,
        server_key=server_key,
        raw=row,
    )


def parse_server_list(payload: Any, *, now: datetime | None = None) -> AsaSnapshot:
    fetched_at = now or datetime.now(timezone.utc)
    if payload is None:
        return AsaSnapshot(fetch_ok=False, fetched_at=fetched_at, error="invalid_json")
    if not isinstance(payload, list):
        return AsaSnapshot(fetch_ok=False, fetched_at=fetched_at, error="not_list")
    if len(payload) == 0:
        return AsaSnapshot(
            fetch_ok=True,
            fetched_at=fetched_at,
            servers=(),
            error="empty",
            server_count=0,
        )
    servers: list[AsaServer] = []
    skipped = 0
    for row in payload:
        parsed = parse_asa_server(row, now=fetched_at)
        if parsed is None:
            skipped += 1
            continue
        servers.append(parsed)
    if skipped:
        logger.warning("Skipped %s malformed official-list entries", skipped)
    return AsaSnapshot(
        fetch_ok=True,
        fetched_at=fetched_at,
        servers=tuple(servers),
        server_count=len(servers),
        skipped=skipped,
    )


def fetch_official_snapshot() -> AsaSnapshot:
    now = datetime.now(timezone.utc)
    resp = fetch_url(config.SERVER_LIST_URL, timeout=20)
    if resp is None:
        return AsaSnapshot(fetch_ok=False, fetched_at=now, error="fetch_failed")
    try:
        payload = resp.json()
    except ValueError:
        logger.warning("Official server list was not valid JSON")
        return AsaSnapshot(fetch_ok=False, fetched_at=now, error="invalid_json")
    snapshot = parse_server_list(payload, now=now)
    if snapshot.fetch_ok:
        logger.info(
            "Official ASA list refresh ok (%s servers, skipped %s)",
            snapshot.server_count,
            snapshot.skipped,
        )
    return snapshot


def parse_network_status(text: str, *, fetch_ok: bool = True) -> NetworkStatus:
    raw = text or ""
    if not fetch_ok:
        return NetworkStatus(fetch_ok=False, online=None, version=None, raw=raw, error="fetch_failed")
    match = _NETWORK_STATUS_RE.search(raw)
    if not match:
        return NetworkStatus(fetch_ok=True, online=None, version=None, raw=raw, error="parse_failed")
    online = match.group(1).lower() == "online"
    version = match.group(2)
    if version and not version.lower().startswith("v"):
        version = f"v{version}"
    return NetworkStatus(fetch_ok=True, online=online, version=version, raw=raw)


def fetch_network_status() -> NetworkStatus:
    resp = fetch_url(config.NETWORK_STATUS_URL)
    if resp is None:
        return NetworkStatus(fetch_ok=False, online=None, version=None, error="fetch_failed")
    return parse_network_status(resp.text, fetch_ok=True)


def parse_announcement(text: str, *, fetch_ok: bool = True) -> AsaAnnouncement:
    if not fetch_ok:
        return AsaAnnouncement(fetch_ok=False, text=None, error="fetch_failed")
    raw = _BR_RE.sub("\n", text or "")
    stripped = _HTML_TAG_RE.sub(" ", raw)
    lines = [" ".join(line.split()) for line in stripped.splitlines()]
    stripped = "\n".join(line for line in lines if line).strip()
    if stripped.lower() in _EMPTY_NOTICE:
        return AsaAnnouncement(fetch_ok=True, text=None)
    return AsaAnnouncement(fetch_ok=True, text=stripped[:_ANNOUNCEMENT_MAX] or None)


def fetch_announcement() -> AsaAnnouncement:
    resp = fetch_url(config.NOTIFICATION_URL)
    if resp is None:
        return AsaAnnouncement(fetch_ok=False, text=None, error="fetch_failed")
    return parse_announcement(resp.text, fetch_ok=True)
