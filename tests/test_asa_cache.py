from __future__ import annotations

from datetime import datetime, timezone

from functions.asa_cache import (
    current_network,
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


def test_refresh_single_flight(monkeypatch):
    """Concurrent refreshers share one CDN fetch instead of duplicating the list in RAM."""
    import threading
    import time

    reset_asa_cache()
    started = threading.Event()
    release = threading.Event()
    calls = {"n": 0}
    good = parse_server_list(
        [
            {
                "SessionName": "EU-PVE-TheIsland5313 - (v92.43)",
                "Name": "EU-PVE-TheIsland5313",
                "SessionID": "abc",
                "IP": "1.1.1.1",
                "NumPlayers": 3,
                "MaxPlayers": 70,
                "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        ]
    )

    def slow_fetch():
        calls["n"] += 1
        started.set()
        assert release.wait(timeout=2)
        time.sleep(0.05)
        return good

    monkeypatch.setattr("functions.asa_cache.fetch_official_snapshot", slow_fetch)
    monkeypatch.setattr(
        "functions.asa_cache.fetch_network_status",
        lambda: NetworkStatus(fetch_ok=True, online=True, version="v92.43"),
    )
    monkeypatch.setattr(
        "functions.asa_cache.fetch_announcement",
        lambda: AsaAnnouncement(fetch_ok=True, text=None),
    )

    results: list[AsaSnapshot] = []

    def worker():
        results.append(refresh_asa_cache())

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    assert started.wait(timeout=2)
    t2.start()
    time.sleep(0.05)
    release.set()
    t1.join(timeout=2)
    t2.join(timeout=2)
    assert calls["n"] == 1
    assert len(results) == 2
    assert all(r.fetch_ok and r.server_count == 1 for r in results)
    reset_asa_cache()


def test_cache_keeps_last_good_network_on_failure(monkeypatch):
    reset_asa_cache()
    good_net = NetworkStatus(fetch_ok=True, online=True, version="v92.43")
    bad_net = NetworkStatus(fetch_ok=False, online=None, version=None, error="fetch_failed")
    good = parse_server_list(
        [
            {
                "SessionName": "EU-PVE-TheIsland5313 - (v92.43)",
                "Name": "EU-PVE-TheIsland5313",
                "SessionID": "abc",
                "IP": "1.1.1.1",
                "NumPlayers": 3,
                "MaxPlayers": 70,
                "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
            }
        ]
    )
    failed = AsaSnapshot(fetch_ok=False, fetched_at=datetime.now(timezone.utc), error="fetch_failed")
    snap_calls = {"n": 0}

    def fake_fetch():
        snap_calls["n"] += 1
        return good if snap_calls["n"] == 1 else failed

    monkeypatch.setattr("functions.asa_cache.fetch_official_snapshot", fake_fetch)
    net_calls = {"n": 0}

    def fake_net():
        net_calls["n"] += 1
        return good_net if net_calls["n"] == 1 else bad_net

    monkeypatch.setattr("functions.asa_cache.fetch_network_status", fake_net)
    monkeypatch.setattr(
        "functions.asa_cache.fetch_announcement",
        lambda: AsaAnnouncement(fetch_ok=True, text="maintenance"),
    )
    refresh_asa_cache(force=True)
    assert current_network() is not None
    assert current_network().fetch_ok
    refresh_asa_cache(force=True)
    assert current_network() is not None
    assert current_network().fetch_ok
    assert current_network().label == "ONLINE"
    reset_asa_cache()


def test_to_raw_dict_round_trip():
    reset_asa_cache()
    row = {
        "SessionName": "EU-PVE-TheIsland5313 - (v92.43)",
        "Name": "EU-PVE-TheIsland5313",
        "SessionID": "abc",
        "IP": "1.1.1.1",
        "Port": 7777,
        "NumPlayers": 3,
        "MaxPlayers": 70,
        "MapName": "TheIsland_WP",
        "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "IsOfficial": "1",
        "AllowDownloadChars": "1",
        "Battleye": True,
        "SearchHandle": "noise",
    }
    snap = parse_server_list([row])
    assert snap.server_count == 1
    server = snap.servers[0]
    assert "raw" not in server.__dataclass_fields__
    slim = server.to_raw_dict()
    assert server.raw["SessionID"] == "abc"
    assert "AllowDownloadChars" not in slim
    assert "Battleye" not in slim
    assert slim["SessionID"] == "abc"
    again = parse_server_list([slim])
    assert again.servers[0].server_key == server.server_key
    assert again.servers[0].num_players == 3
    reset_asa_cache()
