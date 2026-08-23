from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from commands.core import cache_sync


def test_startup_reconciliation_delay_uses_configured_grace_and_jitter(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        cache_sync.config, "JSON_CACHE_STARTUP_GRACE_SECONDS", 10.0
    )
    monkeypatch.setattr(
        cache_sync.config, "JSON_CACHE_STARTUP_JITTER_SECONDS", 20.0
    )
    monkeypatch.setattr(cache_sync.random, "uniform", lambda low, high: 7.5)

    assert cache_sync._startup_delay() == 17.5


def test_reconciliation_loop_uses_configured_interval(monkeypatch) -> None:
    monkeypatch.setattr(cache_sync.config, "JSON_CACHE_RECONCILE_SECONDS", 123.0)

    assert cache_sync._reconcile_interval() == 123.0


@pytest.mark.asyncio
async def test_reconciliation_offloads_all_sync_work(monkeypatch) -> None:
    cog = object.__new__(cache_sync.CacheSync)
    to_thread = AsyncMock(return_value=({}, {}, {"db_hits": 0}))
    monkeypatch.setattr(cache_sync.asyncio, "to_thread", to_thread)

    await cache_sync.CacheSync.reconcile.coro(cog)

    to_thread.assert_awaited_once_with(cache_sync._run_reconciliation)


def test_reconciliation_returns_diagnostics_and_stats(monkeypatch) -> None:
    monkeypatch.setattr(cache_sync, "verify_cached_db_state", lambda: {"key": False})
    monkeypatch.setattr(
        cache_sync.cache,
        "diagnostics_snapshot",
        lambda: {"key": {"source": "database-reconcile", "age_seconds": 0.1}},
    )
    monkeypatch.setattr(
        cache_sync.cache, "stats_snapshot", lambda: {"repairs": 1}
    )

    result, diagnostics, stats = cache_sync._run_reconciliation()

    assert result == {"key": False}
    assert diagnostics["key"]["source"] == "database-reconcile"
    assert stats == {"repairs": 1}
