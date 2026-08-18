"""Individual vs global ASA status — isolated so it can change without Discord rewrites."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from functions.asa_models import AsaServer, AsaSnapshot, NetworkStatus

logger = logging.getLogger(__name__)

# Presence heuristic only — the official list has no explicit per-server online flag.
STATUS_ONLINE = "ONLINE"
STATUS_OFFLINE = "OFFLINE"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_API_UNAVAILABLE = "API_UNAVAILABLE"

_miss_lock = threading.Lock()
_miss_counts: dict[str, int] = {}
_last_status: dict[str, str] = {}
_last_version: dict[str, str | None] = {}


def reset_status_tracker() -> None:
    with _miss_lock:
        _miss_counts.clear()
        _last_status.clear()
        _last_version.clear()


def miss_count(server_key: str) -> int:
    with _miss_lock:
        return int(_miss_counts.get(server_key, 0))


@dataclass(frozen=True)
class ServerPresenceStatus:
    status: str
    reason: str
    server: AsaServer | None = None
    from_last_known: bool = False
    network: str = "UNKNOWN"

    @property
    def is_online(self) -> bool:
        return self.status == STATUS_ONLINE

    @property
    def is_offline(self) -> bool:
        return self.status == STATUS_OFFLINE


def _record_transition(server_key: str, new_status: str, *, version: str | None = None) -> None:
    with _miss_lock:
        prev = _last_status.get(server_key)
        prev_ver = _last_version.get(server_key)
        _last_status[server_key] = new_status
        if version is not None:
            _last_version[server_key] = version
    if prev and prev != new_status:
        logger.info("ASA server %s: %s → %s", server_key, prev, new_status)
    if version and prev_ver and prev_ver != version:
        logger.info("ASA server %s version: %s → %s", server_key, prev_ver, version)


def note_found(server_key: str) -> None:
    with _miss_lock:
        _miss_counts[server_key] = 0


def note_missing(server_key: str) -> int:
    with _miss_lock:
        n = _miss_counts.get(server_key, 0) + 1
        _miss_counts[server_key] = n
        return n


def get_server_status(
    server: AsaServer | None,
    *,
    snapshot: AsaSnapshot | None,
    network: NetworkStatus | None,
    last_known: AsaServer | None = None,
    server_key: str = "",
    now: datetime | None = None,
    miss_threshold: int | None = None,
    stale_seconds: float | None = None,
    record: bool = True,
) -> ServerPresenceStatus:
    """
    Infer presence from the official list. This is NOT an authoritative
    per-server heartbeat — Wildcard does not publish an explicit online flag.
    """
    import config

    now = now or datetime.now(timezone.utc)
    threshold = config.ASA_OFFLINE_MISS_THRESHOLD if miss_threshold is None else miss_threshold
    stale = float(config.ASA_STALE_SECONDS if stale_seconds is None else stale_seconds)
    net_label = network.label if network else "UNKNOWN"
    key = server_key or (server.server_key if server else "") or (
        last_known.server_key if last_known else ""
    )

    if snapshot is None or not snapshot.fetch_ok:
        if record and key:
            _record_transition(key, STATUS_API_UNAVAILABLE, version=last_known.version if last_known else None)
        return ServerPresenceStatus(
            status=STATUS_API_UNAVAILABLE,
            reason="official_list_unavailable",
            server=last_known,
            from_last_known=last_known is not None,
            network=net_label,
        )

    if network is not None and network.fetch_ok and network.online is False:
        # Network-wide downtime: never promote individual servers to OFFLINE.
        if record and key:
            _record_transition(
                key,
                STATUS_UNKNOWN,
                version=(server or last_known).version if (server or last_known) else None,
            )
        return ServerPresenceStatus(
            status=STATUS_UNKNOWN,
            reason="official_network_offline",
            server=server or last_known,
            from_last_known=server is None and last_known is not None,
            network=net_label,
        )

    if server is not None:
        age = server.last_updated_age_seconds
        if age is None and server.last_updated is not None:
            age = max(0.0, (now - server.last_updated).total_seconds())
        if age is not None and age > stale:
            if record and key:
                _record_transition(key, STATUS_UNKNOWN, version=server.version)
            return ServerPresenceStatus(
                status=STATUS_UNKNOWN,
                reason="stale_last_updated",
                server=server,
                network=net_label,
            )
        if record and key:
            note_found(key)
            _record_transition(key, STATUS_ONLINE, version=server.version)
        return ServerPresenceStatus(
            status=STATUS_ONLINE,
            reason="present_in_official_list",
            server=server,
            network=net_label,
        )

    # Missing from a successful list.
    misses = note_missing(key) if (record and key) else (miss_count(key) + 1 if key else 1)
    if misses < max(1, int(threshold)):
        status = STATUS_UNKNOWN
        reason = "missing_from_list_pending"
    else:
        status = STATUS_OFFLINE
        reason = "missing_from_list"
    if record and key:
        _record_transition(key, status, version=last_known.version if last_known else None)
        if status == STATUS_OFFLINE and misses == max(1, int(threshold)):
            logger.info("Monitored ASA server missing → OFFLINE: %s (misses=%s)", key, misses)
    return ServerPresenceStatus(
        status=status,
        reason=reason,
        server=last_known,
        from_last_known=last_known is not None,
        network=net_label,
    )
