from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

from functions.battlemetrics import BattleMetricsUptime
from functions.outage_form import (
    build_outage_report_url,
    current_outage_minutes,
    duration_choice_from_history,
    map_from_name,
    mode_from_name,
    region_from_name,
    server_number_from_resolved,
)
from functions.server_status import ResolvedServer


def test_region_mode_map_from_query():
    assert region_from_name("EU-PVE-TheIsland5313 - (v92.43)") == "EU"
    assert region_from_name("Asia-PVP-Ragnarok10") == "Asia"
    assert mode_from_name("NA-PVP-SmallTribes-TheIsland9270") == "Small Tribes"
    assert mode_from_name("EU-PVE-TheIsland5313") == "PVE"
    assert mode_from_name("EU-PVP-Arkpocalypse-TheCenter12") == "ARKpocalypse"
    assert mode_from_name("EU-PVP-SOTFSolos-TheIsland205") == "SOTF"
    assert map_from_name("TheIsland_WP") == "The Island"
    assert map_from_name("LostColony") == "Lost Colony"
    assert map_from_name("Genesis") == "Genesis 1"


def test_build_outage_report_url_prefills_known_fields():
    resolved = ResolvedServer(
        session_name="EU-PVE-TheIsland5313 - (v92.43)",
        server_key="5313",
        query="5313",
        map_name="TheIsland",
        ip="5.62.112.69",
        platform="PC+XSX+WINGDK+PS5",
    )
    url = build_outage_report_url(resolved, discord_username="wonder")
    assert len(url) <= 512
    params = parse_qs(urlsplit(url).query)
    assert params["entry.472752241"] == ["EU"]
    assert params["entry.1873349371"] == ["PVE"]
    assert params["entry.1678916340"] == ["The Island"]
    assert params["entry.1668883225"] == ["5313"]
    assert params["entry.1746633654"] == ["0-30 minutes"]
    assert params["entry.639417572"] == ["Offline/Down/Crashed"]
    assert params["entry.233908548"] == ["wonder"]
    extra = params["entry.1489095573"][0]
    assert "5313" in extra
    assert "5.62.112.69" in extra
    assert "entry.1766692705" not in params  # never prefill the player's IP
    assert server_number_from_resolved(resolved) == "5313"


def _history(*pcts: float, step_minutes: int = 60) -> list[tuple[datetime, float]]:
    end = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    n = len(pcts)
    return [
        (end - timedelta(minutes=step_minutes * (n - 1 - i)), pct)
        for i, pct in enumerate(pcts)
    ]


def test_duration_from_battlemetrics_history():
    assert duration_choice_from_history([]) == "0-30 minutes"
    assert duration_choice_from_history(_history(100.0, 100.0)) == "0-30 minutes"
    assert current_outage_minutes(_history(100.0, 75.0)) == 15  # 15 min down in last hour
    assert duration_choice_from_history(_history(100.0, 75.0)) == "0-30 minutes"
    assert current_outage_minutes(_history(100.0, 25.0)) == 45
    assert duration_choice_from_history(_history(100.0, 25.0)) == "31 minutes - 1 hour"
    assert duration_choice_from_history(_history(100.0, 0.0, 0.0)) == "1 hour - 3 hours"
    assert duration_choice_from_history(_history(100.0, 0.0, 0.0, 0.0, 0.0)) == "3 hours+"


def test_build_outage_report_url_uses_bm_outage_length():
    end = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    history = [
        (end - timedelta(hours=2), 100.0),
        (end - timedelta(hours=1), 0.0),
        (end, 0.0),
    ]
    resolved = ResolvedServer(
        session_name="EU-PVE-TheIsland5313 - (v92.43)",
        server_key="5313",
        query="5313",
        map_name="TheIsland",
        bm=BattleMetricsUptime(
            server_id="42",
            name=None,
            url="",
            uptime_7=None,
            uptime_30=None,
            uptime_90=None,
            history=history,
        ),
    )
    url = build_outage_report_url(resolved)
    params = parse_qs(urlsplit(url).query)
    assert params["entry.1746633654"] == ["1 hour - 3 hours"]
    assert "BM down" in params["entry.1489095573"][0]
