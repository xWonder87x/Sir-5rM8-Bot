"""Internal ASA models — Discord code should use these, not raw CDN JSON."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AsaServer:
    """Mapped official-list row. `raw` is the original dict for legacy helpers."""

    session_id: str
    name: str
    session_name: str
    ip: str
    port: int | None
    map_name: str
    num_players: int
    max_players: int
    ping: int | None
    build_id: int | None
    minor_build_id: int | None
    version: str | None
    platform: str
    cluster_id: str
    day_time: str
    last_updated: datetime | None
    last_updated_age_seconds: float | None
    is_official: bool
    session_is_pve: bool | None
    server_key: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def ip_port(self) -> str | None:
        if not self.ip:
            return None
        if self.port is None:
            return self.ip
        return f"{self.ip}:{self.port}"


@dataclass(frozen=True)
class NetworkStatus:
    fetch_ok: bool
    online: bool | None  # True/False if parsed, None if unknown/unparsed
    version: str | None
    raw: str = ""
    error: str | None = None  # "fetch_failed" | "parse_failed"

    @property
    def label(self) -> str:
        if not self.fetch_ok:
            return "API_UNAVAILABLE"
        if self.online is True:
            return "ONLINE"
        if self.online is False:
            return "OFFLINE"
        return "UNKNOWN"


@dataclass(frozen=True)
class AsaAnnouncement:
    fetch_ok: bool
    text: str | None
    error: str | None = None


@dataclass(frozen=True)
class AsaSnapshot:
    fetch_ok: bool
    fetched_at: datetime
    servers: tuple[AsaServer, ...] = ()
    error: str | None = None  # "fetch_failed" | "invalid_json" | "empty" | "not_list"
    server_count: int = 0
    skipped: int = 0

    def by_key(self) -> dict[str, AsaServer]:
        return {s.server_key: s for s in self.servers if s.server_key}

    def as_raw_list(self) -> list[dict]:
        return [s.raw for s in self.servers if s.raw]
