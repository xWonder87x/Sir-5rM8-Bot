from __future__ import annotations

from datetime import datetime, timedelta, timezone

from functions.asa import server_key_from_server
from functions.battlemetrics import (
    _parse_uptime_includes,
    fill_uptime_series,
    window_uptime_average,
)
from functions.charts import render_server_status_chart


def test_server_key_prefers_number():
    server = {"SessionName": "EU-PVE-TheIsland5313 - (v88.23)"}
    assert server_key_from_server(server) == "5313"


def test_server_key_falls_back_to_name():
    server = {"SessionName": "CustomPrivateBox"}
    assert server_key_from_server(server) == "CustomPrivateBox"


def test_fill_uptime_series_spans_full_window():
    stop = datetime(2026, 8, 17, 5, 0, tzinfo=timezone.utc)
    start = stop - timedelta(days=7)
    dip = datetime(2026, 8, 17, 4, 0, tzinfo=timezone.utc)
    filled = fill_uptime_series(
        [(dip, 0.0)],
        start=start,
        stop=stop,
        resolution_minutes=60,
    )
    assert len(filled) >= 7 * 24
    assert filled[0][0] <= start + timedelta(hours=1)
    assert filled[-1][0] >= stop - timedelta(hours=1)
    by_hour = {ts: pct for ts, pct in filled}
    assert by_hour[dip] == 0.0
    online = [pct for ts, pct in filled if ts != dip]
    assert all(pct == 100.0 for pct in online)


def test_window_uptime_average():
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    history = [(now - timedelta(hours=i), 100.0 if i else 50.0) for i in range(48)]
    history.sort(key=lambda p: p[0])
    avg = window_uptime_average(history, days=2)
    assert avg is not None
    assert 90.0 < avg <= 100.0


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
