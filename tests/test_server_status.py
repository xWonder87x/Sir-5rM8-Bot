from __future__ import annotations

from functions.battlemetrics import BattleMetricsUptime
from functions.server_status import resolve_server_status


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


def test_resolve_online_from_official_list(monkeypatch):
    server = {
        "SessionName": "EU-PVE-TheIsland5313 - (v88.23)",
        "NumPlayers": 10,
        "MaxPlayers": 70,
        "IP": "1.1.1.1",
        "DayTime": "50",
        "ServerPing": 20,
        "MapName": "TheIsland_WP",
        "PlatformType": "PC",
    }
    monkeypatch.setattr("functions.server_status.fetch_official_servers", lambda: [server])
    monkeypatch.setattr("functions.server_status.fetch_server_uptime_from_asa", lambda _s: _bm())
    resolved = resolve_server_status("5313")
    assert resolved.ok
    assert resolved.online is True
    assert resolved.server_key == "5313"
    assert resolved.num_players == 10
    assert resolved.map_name == "TheIsland"


def test_resolve_offline_numeric_still_shows_status(monkeypatch):
    monkeypatch.setattr("functions.server_status.fetch_official_servers", lambda: [])
    monkeypatch.setattr("functions.server_status.fetch_server_uptime_from_query", lambda _q: _bm())
    resolved = resolve_server_status("5313")
    assert resolved.ok
    assert resolved.online is False
    assert resolved.server_key == "5313"
    assert resolved.num_players == 0
    assert resolved.ip == "1.2.3.4"


def test_resolve_unknown_name_is_not_found(monkeypatch):
    monkeypatch.setattr("functions.server_status.fetch_official_servers", lambda: [])
    monkeypatch.setattr(
        "functions.server_status.fetch_server_uptime_from_query",
        lambda _q: _bm(server_id="", name=None, url="", error="not_found", ip=None, max_players=None, map_name=None),
    )
    resolved = resolve_server_status("zzzznotaserver")
    assert resolved.error == "not_found"


def test_resolve_fetch_failed_does_not_guess(monkeypatch):
    monkeypatch.setattr("functions.server_status.fetch_official_servers", lambda: None)
    resolved = resolve_server_status("5313")
    assert resolved.error == "fetch_failed"
