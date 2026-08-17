from __future__ import annotations

from datetime import datetime, timedelta, timezone

from functions.asa import server_key_from_server
from functions.battlemetrics import _parse_uptime_includes
from functions.charts import render_server_status_chart


def test_server_key_prefers_number():
    server = {"SessionName": "EU-PVE-TheIsland5313 - (v88.23)"}
    assert server_key_from_server(server) == "5313"


def test_server_key_falls_back_to_name():
    server = {"SessionName": "CustomPrivateBox"}
    assert server_key_from_server(server) == "CustomPrivateBox"


def test_parse_uptime_includes_scales_fraction():
    payload = {
        "included": [
            {"type": "serverUptime", "id": "42-7", "attributes": {"value": 0.995}},
            {"type": "serverUptime", "id": "42-30", "attributes": {"value": 99.1}},
        ]
    }
    windows = _parse_uptime_includes(payload)
    assert abs(windows[7] - 99.5) < 0.01
    assert abs(windows[30] - 99.1) < 0.01


def test_render_server_status_chart_png_bytes():
    now = datetime.now(timezone.utc)
    history = [
        (now - timedelta(hours=6), 99.5),
        (now - timedelta(hours=3), 97.0),
        (now, 100.0),
    ]
    png = render_server_status_chart(
        session_name="EU-PVE-TheIsland5313",
        num_players=30,
        max_players=70,
        uptime_history=history,
        history_days=7,
        uptime_7=99.5,
        uptime_30=98.2,
        uptime_90=97.1,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_server_status_chart_with_sparse_history():
    png = render_server_status_chart(
        session_name="EU-PVE-TheIsland5313",
        num_players=5,
        max_players=70,
        uptime_history=[],
        history_days=7,
        status_message="Set BATTLEMETRICS_TOKEN to load uptime history.",
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
