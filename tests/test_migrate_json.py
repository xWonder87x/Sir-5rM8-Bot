from __future__ import annotations

import json
from pathlib import Path

import pytest

import config
from db.migrate_json import (
    MigrationSummary,
    collect_json_payload,
    json_data_exists,
    preview_migration,
)


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr("db.migrate_json.CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(
        "db.migrate_json.KARMA_HISTORY_FILE", tmp_path / "karma_history.jsonl"
    )
    monkeypatch.setattr(
        "db.migrate_json.RATE_STATE_FILE",
        tmp_path / "rate_state" / "previous_values.json",
    )
    return tmp_path


def test_json_data_exists_false_when_empty(data_dir: Path):
    assert json_data_exists() is False


def test_collect_json_payload_maps_guilds_karma_and_rate_state(data_dir: Path):
    (data_dir / "rate_state").mkdir()
    (data_dir / "config.json").write_text(
        json.dumps(
            {
                "version": 1,
                "guilds": {
                    "111": {
                        "rate_notifications": {
                            "channel_id": "222",
                            "role_id": "333",
                        }
                    }
                },
                "karma": {
                    "balances": {"999": 4},
                    "cooldowns": {"1:2": "2025-02-11T12:00:00"},
                    "cooldown_hours": 12,
                    "history_limit": 5,
                },
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "karma_history.jsonl").write_text(
        json.dumps(
            {
                "user_id": "999",
                "timestamp": "2025-02-11T14:30:00",
                "action": "add",
                "amount": 1,
                "by": "Alice",
                "giver_id": "1",
                "reason": "helped",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "rate_state" / "previous_values.json").write_text(
        json.dumps({"XPMultiplier": 2.0}),
        encoding="utf-8",
    )

    payload = collect_json_payload()
    summary = MigrationSummary.from_payload(payload)

    assert summary.guild_notifications == 1
    assert summary.balances == 1
    assert summary.cooldowns == 1
    assert summary.events == 1
    assert summary.has_rate_state is True
    assert summary.cooldown_hours == 12
    assert summary.history_limit == 5
    assert payload["guild_notifications"][0]["guild_id"] == "111"


def test_preview_migration_requires_supabase(data_dir: Path, monkeypatch: pytest.MonkeyPatch):
    (data_dir / "config.json").write_text('{"version":1,"guilds":{}}', encoding="utf-8")
    monkeypatch.setattr("db.migrate_json.use_supabase", lambda: False)

    with pytest.raises(Exception, match="SUPABASE_URL"):
        preview_migration()
