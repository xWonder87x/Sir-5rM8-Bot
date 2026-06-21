from __future__ import annotations

from unittest.mock import patch

import functions


def test_check_rate_changes_saves_baseline_when_no_previous():
    current = {key: "1" for key in ("XPMultiplier", "HarvestAmountMultiplier")}
    with patch("functions.fetch_current_rates", return_value=current):
        with patch("db.get_previous_rate_values", return_value=None):
            with patch("db.save_previous_rate_values") as save:
                result = functions.check_rate_changes()
    assert result == (None, None, None, 1)
    save.assert_called_once_with(current)


def test_check_rate_changes_detects_difference():
    previous = {"XPMultiplier": "1", "HarvestAmountMultiplier": "1"}
    current = {"XPMultiplier": "2", "HarvestAmountMultiplier": "1"}
    channels = [{"server_id": "1", "channel_id": "2", "role": "3"}]
    with patch("functions.fetch_current_rates", return_value=current):
        with patch("db.get_previous_rate_values", return_value=previous):
            with patch("db.save_previous_rate_values"):
                with patch(
                    "db.get_rate_notification_channels",
                    return_value=channels,
                ):
                    result = functions.check_rate_changes()
    assert result[3] == 0
    assert result[0] == channels
    assert result[1] == current
    assert result[2] == previous
