from __future__ import annotations

from unittest.mock import Mock

import pytest

from functions import bothunter_cache
from functions import json_db_cache as cache


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    cache.reset()
    yield
    cache.reset()


def test_log_event_updates_aggregate_and_channel_counts(monkeypatch):
    log_event = Mock()
    monkeypatch.setattr(bothunter_cache.db, "log_bothunter_event", log_event)
    cache.put("bothunter_count:10:*", 4)
    cache.put("bothunter_count:10:20", 2)

    bothunter_cache.log_event("10", "30", "20")

    log_event.assert_called_once_with("10", "30", "20")
    assert cache.peek("bothunter_count:10:*") == 5
    assert cache.peek("bothunter_count:10:20") == 3


def test_log_event_without_channel_increments_aggregate_once(monkeypatch):
    monkeypatch.setattr(bothunter_cache.db, "log_bothunter_event", Mock())
    cache.put("bothunter_count:10:*", 4)

    bothunter_cache.log_event("10", "30", None)

    assert cache.peek("bothunter_count:10:*") == 5


def test_log_event_updates_persisted_counts_after_memory_reset(monkeypatch):
    monkeypatch.setattr(bothunter_cache.db, "log_bothunter_event", Mock())
    cache.put("bothunter_count:10:*", 4)
    cache.put("bothunter_count:10:20", 2)
    cache.reset()

    bothunter_cache.log_event("10", "30", "20")

    assert cache.peek("bothunter_count:10:*") == 5
    assert cache.peek("bothunter_count:10:20") == 3


def test_log_event_does_not_seed_count_from_post_write_database_value(monkeypatch):
    monkeypatch.setattr(bothunter_cache.db, "log_bothunter_event", Mock())
    loader = Mock(return_value=9)
    monkeypatch.setattr(
        bothunter_cache.db, "get_bothunter_moderated_count", loader
    )

    bothunter_cache.log_event("10", "30", "20")

    assert bothunter_cache.get_count("10", "20") == 9
    loader.assert_called_once_with("10", "20")


def test_reconcile_verifies_loaded_channel_specific_count(monkeypatch):
    monkeypatch.setattr(
        bothunter_cache.db, "get_bothunter_configs", lambda: {}
    )
    count_loader = Mock(return_value=7)
    monkeypatch.setattr(
        bothunter_cache.db, "get_bothunter_moderated_count", count_loader
    )
    cache.put("bothunter_count:10:20", 3)

    result = bothunter_cache.verify_cached_bothunter_state()

    assert result["bothunter_count:10:20"] is False
    assert cache.peek("bothunter_count:10:20") == 7
    count_loader.assert_called_once_with("10", "20")
