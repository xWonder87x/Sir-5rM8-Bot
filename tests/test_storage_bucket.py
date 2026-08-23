from __future__ import annotations

from db import storage


def test_bucket_name_valid():
    assert storage.bucket_name_valid("my-bucket-123") is True
    assert storage.bucket_name_valid("}") is False
    assert storage.bucket_name_valid("") is False


def test_looks_like_railway_template():
    assert storage.looks_like_railway_template("${{bot-state.BUCKET}}") is True
    assert storage.looks_like_railway_template("${VAR}") is True
    assert storage.looks_like_railway_template("abc123-bucket") is False
