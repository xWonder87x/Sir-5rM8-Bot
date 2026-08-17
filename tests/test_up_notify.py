from __future__ import annotations

import db.files as files


def test_add_up_notify_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(files, "UP_NOTIFY_FILE", tmp_path / "server_up_notify.json")
    monkeypatch.setattr(files, "DATA_DIR", tmp_path)
    assert files.add_up_notify("5313", "1", "10", guild_id="99", query="5313") is True
    assert files.add_up_notify("5313", "1", "10", guild_id="99", query="5313") is False
    assert files.add_up_notify("5313", "2", "10") is True
    assert files.list_up_notify_keys() == ["5313"]
    watchers = files.list_up_notify_watchers("5313")
    assert {w["user_id"] for w in watchers} == {"1", "2"}
    assert files.clear_up_notify("5313", "10") == 2
    assert files.list_up_notify_watchers("5313") == []
