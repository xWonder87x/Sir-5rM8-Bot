from __future__ import annotations

from commands.core.admin import _paginate_lines
import config


def test_paginate_lines_single_page():
    lines = [f"line {i}" for i in range(5)]
    pages = _paginate_lines("**Header:**", lines)
    assert len(pages) == 1
    assert all(f"line {i}" in pages[0] for i in range(5))


def test_paginate_lines_splits_long_list():
    lines = [f"Guild {i} " + ("x" * 120) for i in range(30)]
    pages = _paginate_lines("**Servers (30):**", lines)
    assert len(pages) > 1
    assert all(len(p) <= config.DISCORD_MESSAGE_MAX for p in pages)
    assert "continued 2" in pages[1]
