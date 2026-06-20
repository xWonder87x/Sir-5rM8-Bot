from __future__ import annotations

from utils import constants
from commands.karma import _fit_discord_message, _format_history_line, _truncate_reason


def test_truncate_reason():
    long_reason = "x" * 100
    truncated = _truncate_reason(long_reason)
    assert len(truncated) == constants.KARMA_REASON_DISPLAY_MAX
    assert truncated.endswith("…")


def test_format_history_line_truncates_reason():
    entry = {
        "timestamp": "2025-01-01T12:00:00+00:00",
        "action": "add",
        "amount": 1,
        "by": "Alice",
        "giver_id": "1",
        "reason": "y" * 200,
    }
    line = _format_history_line(entry)
    assert "…" in line


def test_fit_discord_message_drops_oldest_lines():
    header = "**Header:**"
    lines = [f"line {i} " + ("z" * 200) for i in range(20)]
    msg = _fit_discord_message(header, lines)
    assert len(msg) <= constants.DISCORD_MESSAGE_MAX
    assert "omitted" in msg
