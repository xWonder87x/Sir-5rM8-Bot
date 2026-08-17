"""BattleMetrics API client for ASA server uptime stats."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

import config

logger = logging.getLogger(__name__)

_BM_BASE = "https://api.battlemetrics.com"
_GAME_ID = "arksa"


@dataclass(frozen=True)
class BattleMetricsUptime:
    server_id: str
    name: str | None
    url: str
    uptime_7: float | None
    uptime_30: float | None
    uptime_90: float | None
    # points: (timestamp, uptime_percent 0-100)
    history: list[tuple[datetime, float]]
    error: str | None = None  # "no_token" | "not_found" | "fetch_failed"

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.server_id)


def _headers() -> dict[str, str] | None:
    token = (config.BATTLEMETRICS_TOKEN or "").strip()
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "Sir-5rM8/1.0",
    }


def _get(path: str, *, params: dict | None = None) -> dict | None:
    headers = _headers()
    if headers is None:
        return None
    url = f"{_BM_BASE}{path}"
    try:
        resp = requests.get(url, headers=headers, params=params or {}, timeout=15)
        if resp.status_code == 401 or resp.status_code == 403:
            logger.warning("BattleMetrics auth failed (%s)", resp.status_code)
            return None
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("BattleMetrics request failed (%s): %s", url, exc)
        return None


def _parse_uptime_includes(payload: dict) -> dict[int, float]:
    """Map window days -> uptime percent from included serverUptime resources."""
    out: dict[int, float] = {}
    for item in payload.get("included") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "serverUptime":
            continue
        attrs = item.get("attributes") or {}
        value = attrs.get("value")
        # id often looks like "<serverId>-7" / "-30" / "-90"
        raw_id = str(item.get("id") or "")
        days = None
        if "-" in raw_id:
            tail = raw_id.rsplit("-", 1)[-1]
            if tail.isdigit():
                days = int(tail)
        if days is None:
            # fallback: name/detail fields if present
            for key in ("days", "period", "window"):
                if attrs.get(key) is not None:
                    try:
                        days = int(attrs[key])
                    except (TypeError, ValueError):
                        pass
        if days is None or value is None:
            continue
        try:
            out[days] = float(value) * (100.0 if float(value) <= 1.0 else 1.0)
        except (TypeError, ValueError):
            continue
    return out


def find_battlemetrics_server(
    *,
    ip: str | None,
    port: int | None,
    session_name: str | None,
    server_number: str | None,
) -> dict | None:
    """Return best-matching BM server resource (data object), or None."""
    searches: list[str] = []
    if ip:
        searches.append(ip.strip())
    if server_number:
        searches.append(server_number.strip())
    if session_name:
        # strip version suffix for better BM search
        name = session_name.split(" - (")[0].strip()
        if name and name not in searches:
            searches.append(name)

    candidates: list[dict] = []
    seen: set[str] = set()
    for term in searches:
        payload = _get(
            "/servers",
            params={
                "filter[game]": _GAME_ID,
                "filter[search]": term,
                "page[size]": 25,
            },
        )
        if not payload:
            continue
        for row in payload.get("data") or []:
            sid = str(row.get("id") or "")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            candidates.append(row)

    if not candidates:
        return None

    def score(row: dict) -> int:
        attrs = row.get("attributes") or {}
        s = 0
        row_ip = str(attrs.get("ip") or "")
        row_port = attrs.get("port")
        row_query = attrs.get("portQuery")
        row_name = str(attrs.get("name") or "")
        if ip and row_ip == ip:
            s += 100
        if port is not None:
            if row_port == port or row_query == port:
                s += 40
        if server_number and server_number in row_name.replace(" ", ""):
            s += 30
        if session_name:
            base = session_name.split(" - (")[0].strip().lower()
            if base and base in row_name.lower():
                s += 20
        return s

    best = max(candidates, key=score)
    if score(best) <= 0 and not (ip or server_number):
        return None
    # Require at least some signal when we have IP/number
    if (ip or server_number) and score(best) < 20:
        # still accept top search hit if BM ranked it first for our query
        return best
    return best


def fetch_downtime_uptime_history(
    server_id: str,
    *,
    days: int,
    resolution_minutes: int = 60,
) -> list[tuple[datetime, float]]:
    """
    Convert BM downtime seconds into uptime percent points.
    value = seconds offline in the bucket; period = resolution_minutes * 60.
    """
    stop = datetime.now(timezone.utc)
    start = stop - timedelta(days=max(1, int(days)))
    period = max(int(resolution_minutes), 1) * 60
    payload = _get(
        f"/servers/{server_id}/relationships/downtime",
        params={
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stop": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolution": str(int(resolution_minutes)),
        },
    )
    if not payload:
        return []

    points: list[tuple[datetime, float]] = []
    for row in payload.get("data") or []:
        attrs = row.get("attributes") or {}
        ts_raw = attrs.get("timestamp")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            offline = float(attrs.get("value") or 0)
            uptime = 100.0 * (1.0 - min(max(offline, 0.0), float(period)) / float(period))
            points.append((ts, max(0.0, min(100.0, uptime))))
        except (TypeError, ValueError):
            continue
    points.sort(key=lambda p: p[0])
    return points


def fetch_server_uptime(
    *,
    ip: str | None,
    port: int | None,
    session_name: str | None,
    server_number: str | None,
) -> BattleMetricsUptime:
    """Look up a server on BattleMetrics and return uptime summary + history."""
    if not (config.BATTLEMETRICS_TOKEN or "").strip():
        return BattleMetricsUptime(
            server_id="",
            name=None,
            url="",
            uptime_7=None,
            uptime_30=None,
            uptime_90=None,
            history=[],
            error="no_token",
        )

    match = find_battlemetrics_server(
        ip=ip,
        port=port,
        session_name=session_name,
        server_number=server_number,
    )
    if not match:
        return BattleMetricsUptime(
            server_id="",
            name=None,
            url="",
            uptime_7=None,
            uptime_30=None,
            uptime_90=None,
            history=[],
            error="not_found",
        )

    server_id = str(match.get("id"))
    name = (match.get("attributes") or {}).get("name")
    detail = _get(
        f"/servers/{server_id}",
        params={"include": "uptime:7,uptime:30,uptime:90"},
    )
    windows = _parse_uptime_includes(detail) if detail else {}
    history = fetch_downtime_uptime_history(
        server_id,
        days=config.BM_UPTIME_HISTORY_DAYS,
        resolution_minutes=config.BM_UPTIME_RESOLUTION_MINUTES,
    )
    if detail is None and not history:
        return BattleMetricsUptime(
            server_id=server_id,
            name=name,
            url=f"https://www.battlemetrics.com/servers/arksa/{server_id}",
            uptime_7=None,
            uptime_30=None,
            uptime_90=None,
            history=[],
            error="fetch_failed",
        )

    return BattleMetricsUptime(
        server_id=server_id,
        name=str(name) if name else None,
        url=f"https://www.battlemetrics.com/servers/arksa/{server_id}",
        uptime_7=windows.get(7),
        uptime_30=windows.get(30),
        uptime_90=windows.get(90),
        history=history,
        error=None,
    )


def fetch_server_uptime_from_asa(server: dict[str, Any]) -> BattleMetricsUptime:
    from functions.asa import _server_number

    session_name = str(server.get("SessionName") or "") or None
    ip = str(server.get("IP") or "") or None
    port_raw = server.get("Port")
    try:
        port = int(port_raw) if port_raw is not None else None
    except (TypeError, ValueError):
        port = None
    number = _server_number(session_name) if session_name else None
    return fetch_server_uptime(
        ip=ip,
        port=port,
        session_name=session_name,
        server_number=number,
    )
