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
_last_bucket_write_at: float = 0.0
_last_bucket_write_count: int | None = None


def reset_asa_cache() -> None:
    """Test helper — clear process cache."""
    global _snapshot, _last_good, _network, _announcement, _last_network_label
    global _last_bucket_write_at, _last_bucket_write_count
    with _lock:
        _snapshot = None
        _last_good = None
        _network = None
        _announcement = None
        _last_network_label = None
        _last_bucket_write_at = 0.0
        _last_bucket_write_count = None


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


def _hydrate_from_bucket() -> None:
    """Load last-known official list from STATE_BUCKET after a process restart."""
    global _snapshot, _last_good, _network, _announcement
    from functions.asa_client import parse_server_list
    from functions.blob_state import ASA_CACHE_KEY, load_json, state_bucket_configured

    if not state_bucket_configured():
        return
    data = load_json(ASA_CACHE_KEY)
    raw_servers = data.get("servers")
    if not isinstance(raw_servers, list) or not raw_servers:
        return
    fetched_at = None
    raw_ts = data.get("fetched_at")
    if isinstance(raw_ts, str):
        try:
            fetched_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            fetched_at = None
    snap = parse_server_list(raw_servers, now=fetched_at)
    if not snap.fetch_ok or not snap.server_count:
        return
    net_raw = data.get("network") if isinstance(data.get("network"), dict) else {}
    notice_raw = data.get("announcement") if isinstance(data.get("announcement"), dict) else {}
    network = NetworkStatus(
        fetch_ok=bool(net_raw.get("fetch_ok")),
        online=net_raw.get("online"),
        version=net_raw.get("version"),
        raw=str(net_raw.get("raw") or ""),
        error=net_raw.get("error"),
    )
    announcement = AsaAnnouncement(
        fetch_ok=bool(notice_raw.get("fetch_ok", True)),
        text=notice_raw.get("text"),
        error=notice_raw.get("error"),
    )
    with _lock:
        if _last_good is None:
            _last_good = snap
            _snapshot = snap
            _network = network
            _announcement = announcement
            logger.info(
                "ASA cache hydrated from STATE_BUCKET (%s servers)",
                snap.server_count,
            )


def _persist_to_bucket(
    snapshot: AsaSnapshot,
    network: NetworkStatus,
    announcement: AsaAnnouncement,
) -> None:
    import time as time_mod

    import config
    from functions.blob_state import ASA_CACHE_KEY, save_json, state_bucket_configured

    global _last_bucket_write_at, _last_bucket_write_count

    if not state_bucket_configured() or not snapshot.fetch_ok or not snapshot.server_count:
        return
    now = time_mod.monotonic()
    interval = max(0, int(getattr(config, "ASA_BUCKET_FLUSH_SECONDS", 300)))
    with _lock:
        if (
            _last_bucket_write_at
            and _last_bucket_write_count == snapshot.server_count
            and now - _last_bucket_write_at < interval
        ):
            return
        _last_bucket_write_at = now
        _last_bucket_write_count = snapshot.server_count
    payload = {
        "fetched_at": snapshot.fetched_at.isoformat(),
        "servers": snapshot.as_raw_list(),
        "network": {
            "fetch_ok": network.fetch_ok,
            "online": network.online,
            "version": network.version,
            "raw": network.raw,
            "error": network.error,
        },
        "announcement": {
            "fetch_ok": announcement.fetch_ok,
            "text": announcement.text,
            "error": announcement.error,
        },
    }
    if save_json(ASA_CACHE_KEY, payload):
        logger.info(
            "ASA cache flushed to STATE_BUCKET (%s servers)",
            snapshot.server_count,
        )


def refresh_asa_cache(*, force: bool = False) -> AsaSnapshot:
    """Fetch official list + network status. Preserve last-known-good on failure."""
    import time as time_mod

    global _snapshot, _last_good, _network, _announcement, _last_network_label, _last_log_fail_at

    with _lock:
        if not force and snapshot_is_fresh(_snapshot):
            return _snapshot  # type: ignore[return-value]
        need_hydrate = _last_good is None

    if need_hydrate:
        _hydrate_from_bucket()

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
    if snapshot.fetch_ok:
        _persist_to_bucket(snapshot, network, announcement)
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
