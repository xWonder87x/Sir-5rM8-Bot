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


def _to_uptime_percent(value: Any) -> float | None:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= raw <= 1.0:
        raw *= 100.0
    return max(0.0, min(100.0, raw))


def _parse_uptime_includes(payload: dict) -> dict[int, float]:
    """Map window days -> uptime percent from included serverUptime resources."""
    out: dict[int, float] = {}
    for item in payload.get("included") or []:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "")
        if item_type and item_type not in ("serverUptime", "uptime"):
            continue
        attrs = item.get("attributes") or {}
        value = attrs.get("value")
        raw_id = str(item.get("id") or "")
        days = None
        if "-" in raw_id:
            tail = raw_id.rsplit("-", 1)[-1]
            if tail.isdigit():
                days = int(tail)
        if days is None:
            for key in ("days", "period", "window"):
                if attrs.get(key) is not None:
                    try:
                        days = int(attrs[key])
                    except (TypeError, ValueError):
                        pass
        if days not in (7, 30, 90):
            continue
        pct = _to_uptime_percent(value)
        if pct is None:
            continue
        out[days] = pct
    return out


def _align_utc(ts: datetime, minutes: int) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    step = max(int(minutes), 1) * 60
    epoch = int(ts.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % step), tz=timezone.utc)


def fill_uptime_series(
    raw_points: list[tuple[datetime, float]],
    *,
    start: datetime,
    stop: datetime,
    resolution_minutes: int,
) -> list[tuple[datetime, float]]:
    """
    Expand sparse BM downtime buckets into a complete series.
    Missing buckets are treated as 100% uptime (no reported downtime).
    """
    step_min = max(int(resolution_minutes), 1)
    t0 = _align_utc(start, step_min)
    t1 = _align_utc(stop, step_min)
    if t1 < t0:
        t0, t1 = t1, t0
    span_min = max((t1 - t0).total_seconds() / 60.0, 1.0)
    max_points = 4000
    if span_min / step_min > max_points:
        step_min = max(step_min, int(span_min // max_points) or 1)
        t0 = _align_utc(start, step_min)
        t1 = _align_utc(stop, step_min)
    by_ts = {
        _align_utc(ts, step_min): max(0.0, min(100.0, float(pct)))
        for ts, pct in raw_points
    }
    out: list[tuple[datetime, float]] = []
    cursor = t0
    delta = timedelta(minutes=step_min)
    while cursor <= t1:
        out.append((cursor, by_ts.get(cursor, 100.0)))
        cursor += delta
    return out


def window_uptime_average(
    history: list[tuple[datetime, float]],
    *,
    days: int,
) -> float | None:
    if not history:
        return None
    end = history[-1][0]
    cutoff = end - timedelta(days=max(1, int(days)))
    vals = [pct for ts, pct in history if ts >= cutoff]
    if not vals:
        return None
    return sum(vals) / len(vals)


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
    Convert BM downtime seconds into a complete uptime-percent series.
    Missing buckets are filled as 100% online so the graph spans the full window.
    """
    stop = datetime.now(timezone.utc)
    start = stop - timedelta(days=max(1, int(days)))
    # BM only allows 60 (90-day retention) or 1440 (daily, indefinite).
    resolution = 1440 if int(days) > 90 else int(resolution_minutes)
    if resolution not in (60, 1440):
        resolution = 60 if int(days) <= 90 else 1440
    period = resolution * 60
    payload = _get(
        f"/servers/{server_id}/relationships/downtime",
        params={
            "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stop": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolution": str(resolution),
        },
    )
    if payload is None:
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
    return fill_uptime_series(
        points,
        start=start,
        stop=stop,
        resolution_minutes=resolution,
    )


def _fetch_uptime_windows(server_id: str) -> dict[int, float]:
    windows: dict[int, float] = {}
    detail = _get(
        f"/servers/{server_id}",
        params={"include": "uptime:7,uptime:30,uptime:90"},
    )
    if detail:
        windows.update(_parse_uptime_includes(detail))
    if len(windows) < 3:
        stop = datetime.now(timezone.utc)
        start = stop - timedelta(days=90)
        outages = _get(
            f"/servers/{server_id}/relationships/outages",
            params={
                "include": "uptime:7,uptime:30,uptime:90",
                "filter[range]": (
                    f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}:"
                    f"{stop.strftime('%Y-%m-%dT%H:%M:%SZ')}"
                ),
                "page[size]": 1,
            },
        )
        if outages:
            windows.update(_parse_uptime_includes(outages))
    return windows


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
    windows = _fetch_uptime_windows(server_id)
    history = fetch_downtime_uptime_history(
        server_id,
        days=config.BM_UPTIME_HISTORY_DAYS,
        resolution_minutes=config.BM_UPTIME_RESOLUTION_MINUTES,
    )
    if not windows and not history:
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

    uptime_7 = windows[7] if 7 in windows else window_uptime_average(history, days=7)
    uptime_30 = windows[30] if 30 in windows else window_uptime_average(history, days=30)
    uptime_90 = windows[90] if 90 in windows else window_uptime_average(history, days=90)

    return BattleMetricsUptime(
        server_id=server_id,
        name=str(name) if name else None,
        url=f"https://www.battlemetrics.com/servers/arksa/{server_id}",
        uptime_7=uptime_7,
        uptime_30=uptime_30,
        uptime_90=uptime_90,
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
