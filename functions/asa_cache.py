"""In-memory official ASA snapshot cache (last-known-good + TTL)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from functions.asa_client import (
    fetch_announcement,
    fetch_network_status,
    fetch_official_snapshot,
)
from functions.asa_models import AsaAnnouncement, AsaSnapshot, AsaServer, NetworkStatus

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_snapshot: AsaSnapshot | None = None
_last_good: AsaSnapshot | None = None
_network: NetworkStatus | None = None
_announcement: AsaAnnouncement | None = None
_last_network_label: str | None = None
_last_log_fail_at: float = 0.0


def reset_asa_cache() -> None:
    """Test helper — clear process cache."""
    global _snapshot, _last_good, _network, _announcement, _last_network_label
    with _lock:
        _snapshot = None
        _last_good = None
        _network = None
        _announcement = None
        _last_network_label = None


def last_good_snapshot() -> AsaSnapshot | None:
    with _lock:
        return _last_good


def current_snapshot() -> AsaSnapshot | None:
    with _lock:
        return _snapshot


def current_network() -> NetworkStatus | None:
    with _lock:
        return _network


def current_announcement() -> AsaAnnouncement | None:
    with _lock:
        return _announcement


def last_known_server(server_key: str) -> AsaServer | None:
    key = str(server_key or "").strip()
    if not key:
        return None
    with _lock:
        snap = _last_good
    if snap is None:
        return None
    return snap.by_key().get(key)


def _age_seconds(snapshot: AsaSnapshot | None) -> float | None:
    if snapshot is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - snapshot.fetched_at).total_seconds())


def snapshot_is_fresh(snapshot: AsaSnapshot | None, *, ttl_seconds: int | None = None) -> bool:
    import config

    ttl = config.ASA_CACHE_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    age = _age_seconds(snapshot)
    if snapshot is None or age is None:
        return False
    if snapshot.fetch_ok:
        return age <= ttl
    return age <= min(ttl, 15)


def refresh_asa_cache(*, force: bool = False) -> AsaSnapshot:
    """Fetch official list + network status. Preserve last-known-good on failure."""
    import config
    import time as time_mod

    global _snapshot, _last_good, _network, _announcement, _last_network_label, _last_log_fail_at

    with _lock:
        if not force and snapshot_is_fresh(_snapshot):
            return _snapshot  # type: ignore[return-value]

    snapshot = fetch_official_snapshot()
    network = fetch_network_status()
    announcement = fetch_announcement()

    with _lock:
        prev_good = _last_good
        _snapshot = snapshot
        if snapshot.fetch_ok:
            _last_good = snapshot
        _network = network
        _announcement = announcement
        prev_label = _last_network_label

    if network.fetch_ok and network.label != prev_label:
        logger.info(
            "Official ARK network status: %s%s",
            network.label,
            f" ({network.version})" if network.version else "",
        )
        with _lock:
            _last_network_label = network.label
    if snapshot.fetch_ok and prev_good is not None and snapshot.server_count != prev_good.server_count:
        logger.info(
            "Official list size %s → %s",
            prev_good.server_count,
            snapshot.server_count,
        )
    if not snapshot.fetch_ok:
        now = time_mod.monotonic()
        if now - _last_log_fail_at > 60:
            logger.warning(
                "Official ASA list unavailable (%s); keeping last known state",
                snapshot.error,
            )
            _last_log_fail_at = now
    return snapshot


def get_snapshot(*, refresh_if_stale: bool = True) -> AsaSnapshot:
    with _lock:
        snap = _snapshot
    if refresh_if_stale and not snapshot_is_fresh(snap):
        return refresh_asa_cache()
    if snap is None:
        return refresh_asa_cache()
    return snap


def get_usable_servers() -> tuple[list[dict], bool]:
    """
    Raw dicts for matching. Second value is True when this is a live successful fetch
    (not a last-known-good fallback after failure).
    """
    snap = get_snapshot()
    if snap.fetch_ok:
        return snap.as_raw_list(), True
    good = last_good_snapshot()
    if good is not None:
        return good.as_raw_list(), False
    return [], False
