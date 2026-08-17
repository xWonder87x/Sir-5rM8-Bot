"""Resolve ASA server status for /serverstatus (online list + offline BM fallback)."""
from __future__ import annotations

from dataclasses import dataclass

from functions.asa import (
    fetch_official_servers,
    match_server_in_list,
    notify_key_from_server,
    query_server_key,
    query_server_number,
)
from functions.battlemetrics import (
    BattleMetricsUptime,
    fetch_server_uptime_from_asa,
    fetch_server_uptime_from_query,
)


@dataclass(frozen=True)
class ResolvedServer:
    error: str | None = None  # "fetch_failed" | "not_found"
    online: bool = False
    server_key: str = ""
    query: str = ""
    session_name: str = "Unknown"
    ip: str = "—"
    num_players: int = 0
    max_players: int = 70
    day: str = "—"
    ping: str = "—"
    map_name: str = "—"
    platform: str = "—"
    bm: BattleMetricsUptime | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _int_field(value, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _from_asa(data: dict, bm: BattleMetricsUptime, query: str, *, online: bool) -> ResolvedServer:
    ping_raw = data.get("ServerPing", "—")
    return ResolvedServer(
        online=online,
        server_key=notify_key_from_server(data),
        query=query,
        session_name=str(data.get("SessionName") or "Unknown"),
        ip=str(data.get("IP") or "—"),
        num_players=_int_field(data.get("NumPlayers"), 0),
        max_players=_int_field(data.get("MaxPlayers"), 70),
        day=str(data.get("DayTime") or "—"),
        ping=f"{ping_raw} ms",
        map_name=str(data.get("MapName") or "—").replace("_WP", ""),
        platform=str(data.get("PlatformType") or "—"),
        bm=bm,
    )


def resolve_server_status(query: str) -> ResolvedServer:
    q = (query or "").strip()
    servers = fetch_official_servers()
    if servers is None:
        return ResolvedServer(error="fetch_failed", query=q)

    found = match_server_in_list(servers, q) if q else None
    if found:
        return _from_asa(found, fetch_server_uptime_from_asa(found), q, online=True)

    if not q:
        return ResolvedServer(error="not_found", query=q)

    number = query_server_number(q)
    bm = fetch_server_uptime_from_query(q)
    if not number and not bm.ok:
        return ResolvedServer(error="not_found", query=q)

    session = (bm.name if bm.name else None) or q
    return ResolvedServer(
        online=False,
        server_key=query_server_key(session) or query_server_key(q),
        query=q,
        session_name=session,
        ip=bm.ip or "—",
        num_players=0,
        max_players=bm.max_players or 70,
        day="—",
        ping="—",
        map_name=(bm.map_name or "—"),
        platform="—",
        bm=bm,
    )


def resolve_from_asa_server(data: dict, query: str = "") -> ResolvedServer:
    """Build an online status payload from an official-list row (used by the up-checker)."""
    return _from_asa(data, fetch_server_uptime_from_asa(data), query, online=True)
