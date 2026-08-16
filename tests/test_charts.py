from __future__ import annotations

from datetime import datetime, timedelta, timezone

from functions.asa import server_key_from_server
from functions.charts import render_server_status_chart


def test_server_key_prefers_number():
    server = {"SessionName": "EU-PVE-TheIsland5313 - (v88.23)"}
    assert server_key_from_server(server) == "5313"


def test_server_key_falls_back_to_name():
    server = {"SessionName": "CustomPrivateBox"}
    assert server_key_from_server(server) == "CustomPrivateBox"


def test_render_server_status_chart_png_bytes():
    now = datetime.now(timezone.utc)
    history = [
        {
            "sampled_at": (now - timedelta(hours=2)).isoformat(),
            "num_players": 10,
            "max_players": 70,
        },
        {
            "sampled_at": (now - timedelta(hours=1)).isoformat(),
            "num_players": 22,
            "max_players": 70,
        },
        {
            "sampled_at": now.isoformat(),
            "num_players": 30,
            "max_players": 70,
        },
    ]
    png = render_server_status_chart(
        session_name="EU-PVE-TheIsland5313",
        num_players=30,
        max_players=70,
        history=history,
        history_hours=24,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_server_status_chart_with_sparse_history():
    png = render_server_status_chart(
        session_name="EU-PVE-TheIsland5313",
        num_players=5,
        max_players=70,
        history=[],
        history_hours=24,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
