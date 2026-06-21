from __future__ import annotations

from functions.asa import (
    ServerLookupResult,
    _parse_rate_config,
    _score_server,
    _server_number,
)


def test_parse_rate_config_extracts_keys():
    text = """
    ; comment
    XPMultiplier=3
    HarvestAmountMultiplier=2.5
    UnknownKey=99
    """
    parsed = _parse_rate_config(text)
    assert parsed["XPMultiplier"] == "3"
    assert parsed["HarvestAmountMultiplier"] == "2.5"
    assert parsed["UnknownKey"] == "99"


def test_server_number_from_session_name():
    name = "EU-PVE-TheIsland5313 - (v88.23)"
    assert _server_number(name) == "5313"


def test_score_server_prefers_exact_number():
    server = {
        "SessionName": "EU-PVE-TheIsland5313 - (v88.23)",
        "SessionNameUpper": "EU-PVE-THEISLAND5313 - (V88.23)",
    }
    other = {
        "SessionName": "EU-PVE-TheIsland5312 - (v88.23)",
        "SessionNameUpper": "EU-PVE-THEISLAND5312 - (V88.23)",
    }
    assert _score_server(server, "5313") > _score_server(other, "5313")


def test_score_server_substring_match():
    server = {
        "SessionName": "EU-PVE-TheIsland5313 - (v88.23)",
        "SessionNameUpper": "EU-PVE-THEISLAND5313 - (V88.23)",
    }
    assert _score_server(server, "TheIsland") > 0


def test_server_lookup_result_ok():
    assert ServerLookupResult(server={"SessionName": "x"}).ok is True
    assert ServerLookupResult(error="not_found").ok is False
