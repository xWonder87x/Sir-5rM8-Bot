from __future__ import annotations

from functions.asa_client import parse_server_list
from functions.asa_status import STATUS_ONLINE, reset_status_tracker
from functions.battlemetrics import BattleMetricsUptime
from functions.server_status import ResolvedServer, resolve_server_status


def _bm(**overrides) -> BattleMetricsUptime:
    data = dict(
        server_id="42",
        name="EU-PVE-TheIsland5313 - (v88.23)",
        url="https://www.battlemetrics.com/servers/arksa/42",
        uptime_7=99.0,
        uptime_30=98.0,
        uptime_90=97.0,
        history=[],
        error=None,
        ip="1.2.3.4",
        max_players=70,
        map_name="TheIsland",
        status="offline",
    )
    data.update(overrides)
    return BattleMetricsUptime(**data)


def _row():
    from datetime import datetime, timezone

    return {
        "SessionName": "EU-PVE-TheIsland5313 - (v88.23)",
        "Name": "EU-PVE-TheIsland5313",
        "NumPlayers": 10,
        "MaxPlayers": 70,
        "IP": "1.1.1.1",
        "DayTime": "50",
        "ServerPing": 20,
        "MapName": "TheIsland_WP",
        "PlatformType": "PC",
        "LastUpdated": int(datetime.now(timezone.utc).timestamp() * 1000),
        "BuildId": 88,
        "MinorBuildId": 23,
        "SessionID": "abc123",
        "IsOfficial": "1",
        "Port": 7777,
    }


def test_resolve_online_from_official_list(monkeypatch):
    snap = parse_server_list([_row()])
    reset_status_tracker()
    monkeypatch.setattr("functions.server_status.get_snapshot", lambda **_k: snap)
    monkeypatch.setattr("functions.server_status.last_good_snapshot", lambda: snap)
    monkeypatch.setattr("functions.server_status.last_known_server", lambda _k: None)
    monkeypatch.setattr("functions.server_status.current_network", lambda: None)
    monkeypatch.setattr("functions.server_status.current_announcement", lambda: None)
    monkeypatch.setattr("functions.server_status.fetch_server_uptime_from_asa", lambda _s: _bm())
    monkeypatch.setattr("functions.server_status.config.BATTLEMETRICS_TOKEN", "test")
    resolved = resolve_server_status("5313")
    assert resolved.ok
    assert resolved.online is True
    assert resolved.presence == STATUS_ONLINE
    assert resolved.server_key == "5313"
    assert resolved.num_players == 10
    assert resolved.map_name == "TheIsland"


def test_resolve_offline_numeric_still_shows_status(monkeypatch):
    snap = parse_server_list([])
    reset_status_tracker()
    monkeypatch.setattr("functions.server_status.get_snapshot", lambda **_k: snap)
    monkeypatch.setattr("functions.server_status.last_good_snapshot", lambda: snap)
    monkeypatch.setattr("functions.server_status.last_known_server", lambda _k: None)
    monkeypatch.setattr("functions.server_status.current_network", lambda: None)
    monkeypatch.setattr("functions.server_status.current_announcement", lambda: None)
    monkeypatch.setattr("functions.server_status.fetch_server_uptime_from_query", lambda _q: _bm())
    monkeypatch.setattr("functions.server_status.config.BATTLEMETRICS_TOKEN", "test")
    resolved = resolve_server_status("5313")
    assert resolved.ok
    assert resolved.online is False
    assert resolved.server_key == "5313"
    assert resolved.num_players == 0
    assert resolved.ip == "1.2.3.4"


def test_resolve_unknown_name_is_not_found(monkeypatch):
    snap = parse_server_list([])
    reset_status_tracker()
    monkeypatch.setattr("functions.server_status.get_snapshot", lambda **_k: snap)
    monkeypatch.setattr("functions.server_status.last_good_snapshot", lambda: snap)
    monkeypatch.setattr("functions.server_status.last_known_server", lambda _k: None)
    monkeypatch.setattr("functions.server_status.current_network", lambda: None)
    monkeypatch.setattr("functions.server_status.current_announcement", lambda: None)
    monkeypatch.setattr(
        "functions.server_status.fetch_server_uptime_from_query",
        lambda _q: _bm(server_id="", name=None, url="", error="not_found", ip=None, max_players=None, map_name=None),
    )
    resolved = resolve_server_status("zzzznotaserver")
    assert resolved.error == "not_found"


def test_resolve_fetch_failed_does_not_guess(monkeypatch):
    from datetime import datetime, timezone

    from functions.asa_models import AsaSnapshot

    failed = AsaSnapshot(fetch_ok=False, fetched_at=datetime.now(timezone.utc), error="fetch_failed")
    monkeypatch.setattr("functions.server_status.get_snapshot", lambda **_k: failed)
    monkeypatch.setattr("functions.server_status.last_good_snapshot", lambda: None)
    monkeypatch.setattr("functions.server_status.current_network", lambda: None)
    monkeypatch.setattr("functions.server_status.current_announcement", lambda: None)
    resolved = resolve_server_status("5313")
    assert resolved.error == "fetch_failed"


def test_status_embed_builds_when_not_online():
    from commands.community.server import _status_embed_and_chart
    from functions.asa_status import STATUS_API_UNAVAILABLE, STATUS_OFFLINE, STATUS_UNKNOWN

    cases = (
        (STATUS_UNKNOWN, "Server Status Unknown"),
        (STATUS_OFFLINE, "Server Offline"),
        (STATUS_API_UNAVAILABLE, "Server Status Unknown"),
    )
    for status, title in cases:
        embed, png, filename = _status_embed_and_chart(
            ResolvedServer(presence=status, session_name="EU-PVE-TheIsland5313", server_key="5313")
        )
        assert embed.title == title
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert filename.endswith(".png")
