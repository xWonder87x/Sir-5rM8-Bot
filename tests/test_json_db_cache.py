from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from functions import json_db_cache as cache


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    cache.reset()
    yield
    cache.reset()


def test_persisted_json_copy_avoids_loader(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cache.put("example", {"value": 1})
    cache.reset()

    def unexpected_loader():
        raise AssertionError("loader should not run for a persisted cache")

    assert cache.get("example", unexpected_loader) == {"value": 1}


def test_v1_envelope_remains_readable(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    path = tmp_path / "cache" / "db" / "legacy.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"version":1,"data":{"value":"legacy"}}', encoding="utf-8")

    assert cache.get("legacy", lambda: pytest.fail("database loader called")) == {
        "value": "legacy"
    }
    assert cache.diagnostics_snapshot()["legacy"]["version"] == 1


def test_put_writes_v2_freshness_envelope(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    before = time.time()

    assert cache.put("example", {"value": 2}) is True

    payload = json.loads(
        (tmp_path / "cache" / "db" / "example.json").read_text(encoding="utf-8")
    )
    assert payload["version"] == 2
    assert payload["written_at"] >= before
    assert payload["generation"]
    assert payload["source"] == "database-write"
    assert payload["data"] == {"value": 2}


def test_newest_valid_persisted_copy_wins(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    path = tmp_path / "cache" / "db" / "example.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "written_at": 100.0,
                "generation": "local-old",
                "data": {"source": "local"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cache.blob_state, "state_bucket_configured", lambda: True)
    monkeypatch.setattr(
        cache.blob_state,
        "load_json",
        lambda key: {
            "version": 2,
            "written_at": 200.0,
            "generation": "bucket-new",
            "data": {"source": "bucket"},
        },
    )

    assert cache.get("example", lambda: pytest.fail("database loader called")) == {
        "source": "bucket"
    }
    assert cache.diagnostics_snapshot()["example"]["source"] == "bucket"
    assert cache.stats_snapshot()["bucket_hits"] == 1


def test_invalid_newer_copy_is_ignored(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    path = tmp_path / "cache" / "db" / "example.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"version":2,"written_at":100,"generation":"ok","data":"local"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(cache.blob_state, "state_bucket_configured", lambda: True)
    monkeypatch.setattr(
        cache.blob_state,
        "load_json",
        lambda key: {"version": 999, "written_at": 999, "data": "invalid"},
    )

    assert cache.get("example", lambda: pytest.fail("database loader called")) == "local"


def test_concurrent_miss_uses_single_database_loader(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    calls = 0
    calls_lock = threading.Lock()

    def loader():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.02)
        return {"value": 1}

    with ThreadPoolExecutor(max_workers=8) as executor:
        values = list(executor.map(lambda _: cache.get("single", loader), range(8)))

    assert values == [{"value": 1}] * 8
    assert calls == 1
    assert cache.stats_snapshot()["db_hits"] == 1


def test_atomic_update_prevents_lost_updates(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cache.put("counter", 0)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(
            executor.map(
                lambda _: cache.update("counter", lambda: 0, lambda value: value + 1),
                range(40),
            )
        )

    assert cache.peek("counter") == 40


def test_persistence_uses_unique_temp_files_and_serializes_per_key(
    monkeypatch, tmp_path
):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    real_replace = cache.os.replace
    temp_names: list[str] = []
    active = 0
    maximum_active = 0
    guard = threading.Lock()

    def observed_replace(source, destination):
        nonlocal active, maximum_active
        with guard:
            active += 1
            maximum_active = max(maximum_active, active)
            temp_names.append(str(source))
        time.sleep(0.005)
        real_replace(source, destination)
        with guard:
            active -= 1

    monkeypatch.setattr(cache.os, "replace", observed_replace)
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(lambda value: cache.put("ordered", value), range(12)))

    assert maximum_active == 1
    assert len(temp_names) == len(set(temp_names)) == 12
    assert all(name.endswith(".tmp") for name in temp_names)


def test_failed_persistence_is_dirty_and_retryable(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    real_replace = cache.os.replace
    fail = True

    def flaky_replace(source, destination):
        nonlocal fail
        if fail:
            fail = False
            raise OSError("disk unavailable")
        real_replace(source, destination)

    monkeypatch.setattr(cache.os, "replace", flaky_replace)

    assert cache.put("dirty", {"value": 1}) is False
    assert cache.stats_snapshot()["dirty_keys"] == 1
    assert cache.retry_dirty() == {"dirty": True}
    stats = cache.stats_snapshot()
    assert stats["dirty_keys"] == 0
    assert stats["persistence_failures"] == 1
    assert stats["persistence_retries"] == 1


def test_verify_repairs_stale_json_copy(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cache.put("example", {"value": 1})

    assert cache.verify("example", lambda: {"value": 2}) is False
    assert cache.get("example", lambda: {"value": 3}) == {"value": 2}
    assert cache.stats_snapshot()["repairs"] == 1
    assert cache.diagnostics_snapshot()["example"]["source"] == "database-reconcile"


def test_stats_track_memory_local_and_database_hits(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    local_path = tmp_path / "cache" / "db" / "local.json"
    local_path.parent.mkdir(parents=True)
    local_path.write_text(
        '{"version":2,"written_at":1,"generation":"local","data":3}',
        encoding="utf-8",
    )
    assert cache.get("database", lambda: 1) == 1
    assert cache.get("database", lambda: 2) == 1
    assert cache.get("local", lambda: 4) == 3

    stats = cache.stats_snapshot()
    assert stats["local_hits"] == 1
    assert stats["db_hits"] == 1
    assert stats["memory_hits"] == 1
