import pytest

import config


@pytest.fixture(autouse=True)
def _disable_state_bucket_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Keep unit tests off a live Railway bucket even if .env has STATE_BUCKET."""
    monkeypatch.setattr("config.STATE_BUCKET", "")
    monkeypatch.setenv("STATE_BUCKET", "")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
