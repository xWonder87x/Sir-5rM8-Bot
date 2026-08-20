"""Behavioral tests for commands.common.sticky.StickyMessage."""
from __future__ import annotations

import tempfile
from pathlib import Path

import discord
import pytest

from commands.common.sticky import StickyMessage

TITLE = "Sticky X"
BOT_ID = 42


class FakeUser:
    id = BOT_ID


class FakeBot:
    user = FakeUser()


class FakeMsg:
    def __init__(self, mid: int, author_id: int, title: str = TITLE) -> None:
        self.id = mid
        self.pinned = True
        self.author = type("A", (), {"id": author_id})()
        self.embeds = [discord.Embed(title=title)]
        self.edited = False
        self.deleted = False

    async def edit(self, **kwargs) -> None:
        self.edited = True

    async def delete(self) -> None:
        self.deleted = True


class _Resp:
    status = 404
    reason = "nf"


class FakeChannel:
    def __init__(self, msgs: list[FakeMsg]) -> None:
        self._msgs = {m.id: m for m in msgs}
        self._hist = list(msgs)
        self.sent: list[FakeMsg] = []
        self._next = 1000

    async def fetch_message(self, mid: int) -> FakeMsg:
        if mid in self._msgs:
            return self._msgs[mid]
        raise discord.NotFound(_Resp(), "nf")

    async def history(self, limit: int = 100):
        for m in self._hist:
            yield m

    async def send(self, **kwargs) -> FakeMsg:
        self._next += 1
        msg = FakeMsg(self._next, BOT_ID)
        self.sent.append(msg)
        self._msgs[msg.id] = msg
        return msg


def _matcher(msg: discord.Message, bot_id: int) -> bool:
    return (
        msg.author.id == bot_id
        and bool(msg.embeds)
        and (msg.embeds[0].title or "") == TITLE
    )


@pytest.mark.asyncio
async def test_sticky_posts_when_missing() -> None:
    d = Path(tempfile.mkdtemp())
    sp = d / "st.json"
    pinned: list[int] = []

    async def pin(msg: discord.Message) -> None:
        pinned.append(msg.id)

    s = StickyMessage(FakeBot(), state_path=sp, matcher=_matcher, log_label="t", pin=pin)
    ch = FakeChannel([])
    await s.ensure(ch, discord.Embed(title=TITLE))
    assert len(ch.sent) == 1
    assert s.message_id == ch.sent[0].id
    assert sp.exists()
    assert pinned[-1] == s.message_id


@pytest.mark.asyncio
async def test_sticky_edits_in_place() -> None:
    d = Path(tempfile.mkdtemp())
    existing = FakeMsg(555, BOT_ID)
    ch = FakeChannel([existing])
    s = StickyMessage(FakeBot(), state_path=d / "st.json", matcher=_matcher, log_label="t")
    s.message_id = 555
    await s.ensure(ch, discord.Embed(title=TITLE))
    assert existing.edited
    assert not ch.sent


@pytest.mark.asyncio
async def test_sticky_clear() -> None:
    d = Path(tempfile.mkdtemp())
    sp = d / "st.json"
    sp.write_text('{"message_id": "1"}', encoding="ascii")
    s = StickyMessage(FakeBot(), state_path=sp, matcher=_matcher, log_label="t")
    s.message_id = 1
    await s.clear()
    assert s.message_id is None
    assert not sp.exists()
