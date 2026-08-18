from __future__ import annotations

from datetime import datetime, timezone

from functions.asa_cache import (
    get_snapshot,
    last_good_snapshot,
    refresh_asa_cache,
    reset_asa_cache,
)
from functions.asa_client import parse_server_list
from functions.asa_models import AsaAnnouncement, AsaSnapshot, NetworkStatus


def test_cache_keeps_last_good_on_failure(monkeypatch):
    reset_asa_cache()
    good = parse_server_list([
        {
            "SessionName": "EU-PVE-TheIsland5313 - (v92.43)",
            "Name": "EU-PVE-TheIsland5313",
            "SessionID": "abc",
            "IP": "1.1.1.1",
            "NumPlayers": 3,
            "MaxPlayers": 70,
            "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
    ])
    failed = AsaSnapshot(fetch_ok=False, fetched_at=datetime.now(timezone.utc), error="fetch_failed")
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return good if calls["n"] == 1 else failed

    monkeypatch.setattr("functions.asa_cache.fetch_official_snapshot", fake_fetch)
    monkeypatch.setattr(
        "functions.asa_cache.fetch_network_status",
        lambda: NetworkStatus(fetch_ok=True, online=True, version="v92.43"),
    )
    monkeypatch.setattr(
        "functions.asa_cache.fetch_announcement",
        lambda: AsaAnnouncement(fetch_ok=True, text=None),
    )
    first = refresh_asa_cache(force=True)
    assert first.fetch_ok
    assert last_good_snapshot() is not None
    second = refresh_asa_cache(force=True)
    assert second.fetch_ok is False
    assert last_good_snapshot().server_count == 1
    assert get_snapshot(refresh_if_stale=False).fetch_ok is False
