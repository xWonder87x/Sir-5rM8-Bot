from __future__ import annotations

from functions import json_db_cache as cache


def test_persisted_json_copy_avoids_loader(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cache.put("example", {"value": 1})
    cache.reset()

    def unexpected_loader():
        raise AssertionError("loader should not run for a persisted cache")

    assert cache.get("example", unexpected_loader) == {"value": 1}


def test_verify_repairs_stale_json_copy(monkeypatch, tmp_path):
    import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    cache.put("example", {"value": 1})

    assert cache.verify("example", lambda: {"value": 2}) is False
    assert cache.get("example", lambda: {"value": 3}) == {"value": 2}
