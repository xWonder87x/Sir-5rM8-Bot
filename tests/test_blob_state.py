from __future__ import annotations

import json

from functions.blob_state import (
    ASA_CACHE_KEY,
    cache_get,
    cache_replace,
    load_json,
    reset_blob_state,
    save_json,
    state_bucket_configured,
)


def test_state_bucket_unconfigured_without_env(monkeypatch):
    monkeypatch.setattr("config.STATE_BUCKET", "")
    monkeypatch.setattr("functions.blob_state.storage.use_s3_storage", lambda: False)
    assert state_bucket_configured() is False
    assert load_json(ASA_CACHE_KEY) == {}
    assert save_json(ASA_CACHE_KEY, {"a": 1}) is False


def test_cache_replace_flushes_when_configured(monkeypatch):
    reset_blob_state()
    uploaded: list[tuple[str, dict]] = []

    monkeypatch.setattr("config.STATE_BUCKET", "test-bucket")
    monkeypatch.setattr("functions.blob_state.storage.use_s3_storage", lambda: True)
    monkeypatch.setattr(
        "functions.blob_state.storage.storage_upload_bytes",
        lambda bucket, key, body, content_type="application/json", upsert=True: uploaded.append(
            (key, json.loads(body.decode("utf-8")))
        ),
    )
    cache_replace(ASA_CACHE_KEY, {"servers": [{"Name": "x"}]}, flush=True)
    assert uploaded[0][0] == ASA_CACHE_KEY
    assert uploaded[0][1]["servers"][0]["Name"] == "x"
    assert cache_get(ASA_CACHE_KEY)["servers"][0]["Name"] == "x"
    reset_blob_state()


def test_load_json_reads_bucket(monkeypatch):
    reset_blob_state()
    monkeypatch.setattr("config.STATE_BUCKET", "test-bucket")
    monkeypatch.setattr("functions.blob_state.storage.use_s3_storage", lambda: True)
    monkeypatch.setattr(
        "functions.blob_state.storage.storage_download_bytes",
        lambda bucket, key: json.dumps({"message_id": "99"}).encode("utf-8"),
    )
    assert load_json("state/guild_list_message.json") == {"message_id": "99"}
    reset_blob_state()
