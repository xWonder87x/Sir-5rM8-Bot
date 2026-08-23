from __future__ import annotations

from datetime import datetime, timezone

from functions.asa_cache import last_good_snapshot, refresh_asa_cache, reset_asa_cache
from functions.asa_client import parse_server_list
from functions.asa_models import AsaAnnouncement, AsaSnapshot, NetworkStatus
from functions.blob_state import ASA_CACHE_KEY


def _sample_row() -> dict:
    return {
        "SessionName": "EU-PVE-TheIsland5313 - (v92.43)",
        "Name": "EU-PVE-TheIsland5313",
        "SessionID": "abc",
        "IP": "1.1.1.1",
        "NumPlayers": 3,
        "MaxPlayers": 70,
        "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
    }


def test_refresh_hydrates_last_good_from_bucket(monkeypatch):
    reset_asa_cache()
    stored = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "servers": [_sample_row()],
        "network": {
            "fetch_ok": True,
            "online": True,
            "version": "v92.43",
            "raw": "Online",
            "error": None,
        },
        "announcement": {"fetch_ok": True, "text": None, "error": None},
    }

    monkeypatch.setattr(
        "functions.blob_state.state_bucket_configured", lambda: True
    )
    monkeypatch.setattr("functions.blob_state.load_json", lambda key: stored if key == ASA_CACHE_KEY else {})
    monkeypatch.setattr(
        "functions.asa_cache.fetch_official_snapshot",
        lambda: AsaSnapshot(
            fetch_ok=False,
            fetched_at=datetime.now(timezone.utc),
            error="fetch_failed",
        ),
    )
    monkeypatch.setattr(
        "functions.asa_cache.fetch_network_status",
        lambda: NetworkStatus(fetch_ok=False, online=None, version=None, error="fetch_failed"),
    )
    monkeypatch.setattr(
        "functions.asa_cache.fetch_announcement",
        lambda: AsaAnnouncement(fetch_ok=False, text=None, error="fetch_failed"),
    )
    monkeypatch.setattr("functions.blob_state.save_json", lambda *a, **k: False)

    failed = refresh_asa_cache(force=True)
    assert failed.fetch_ok is False
    good = last_good_snapshot()
    assert good is not None
    assert good.server_count == 1
    reset_asa_cache()


def test_refresh_persists_successful_snapshot(monkeypatch):
    reset_asa_cache()
    saved: list[dict] = []
    good = parse_server_list([_sample_row()])

    monkeypatch.setattr("functions.blob_state.state_bucket_configured", lambda: True)
    monkeypatch.setattr(
        "functions.blob_state.save_json",
        lambda key, data: saved.append(data) or True,
    )
    monkeypatch.setattr("functions.blob_state.load_json", lambda key: {})
    monkeypatch.setattr("functions.asa_cache.fetch_official_snapshot", lambda: good)
    monkeypatch.setattr(
        "functions.asa_cache.fetch_network_status",
        lambda: NetworkStatus(fetch_ok=True, online=True, version="v92.43"),
    )
    monkeypatch.setattr(
        "functions.asa_cache.fetch_announcement",
        lambda: AsaAnnouncement(fetch_ok=True, text=None),
    )

    refresh_asa_cache(force=True)
    assert saved
    assert saved[0]["servers"][0]["Name"] == "EU-PVE-TheIsland5313"
    reset_asa_cache()
