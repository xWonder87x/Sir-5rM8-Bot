from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import discord
import pytest

import config
from functions.owner_notify import build_guild_join_embed, notify_restart, post_owner_notice


class _User:
    def __init__(self, user_id: int, name: str) -> None:
        self.id = user_id
        self._name = name

    def __str__(self) -> str:
        return self._name


def test_guild_join_embed_includes_core_fields():
    created = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
    guild = SimpleNamespace(
        id=111,
        name="Ark Tribe",
        member_count=42,
        owner_id=222,
        owner=None,
        created_at=created,
        description="PVE cluster",
        icon=SimpleNamespace(url="https://example.com/icon.png"),
        vanity_url_code="arktribe",
        premium_tier=2,
        premium_subscription_count=7,
        preferred_locale="en-US",
        verification_level=SimpleNamespace(name="medium"),
        text_channels=[1, 2, 3],
        voice_channels=[1],
        features=["COMMUNITY", "NEWS"],
    )
    embed = build_guild_join_embed(
        guild,
        owner=_User(222, "Owner#0001"),
        added_by=_User(333, "Admin#0002"),
        bot_guild_count=5,
    )
    fields = {f.name: f.value for f in embed.fields}
    assert embed.title == "Added to a Discord server"
    assert embed.description == "Ark Tribe"
    assert fields["Server ID"] == "`111`"
    assert fields["Members"] == "42"
    assert "Level 2" in fields["Boosts"]
    assert "Owner#0001" in fields["Owner"]
    assert "`222`" in fields["Owner"]
    assert "Admin#0002" in fields["Added by"]
    assert "<t:1705320000:F>" in fields["Created"]
    assert fields["Description"] == "PVE cluster"
    assert "discord.gg/arktribe" in fields["Vanity URL"]
    assert "Medium" in fields["Locale · verification · channels"]
    assert embed.footer.text == "Now in 5 servers"
    assert embed.thumbnail.url == "https://example.com/icon.png"


class _Channel:
    id = 99

    def __init__(self) -> None:
        self.kwargs: dict | None = None

    async def send(self, **kwargs) -> None:
        self.kwargs = kwargs


@pytest.mark.asyncio
async def test_post_owner_notice_pings_in_channel(monkeypatch):
    channel = _Channel()
    monkeypatch.setattr(config, "RESTART_NOTIFY_USER_ID", 464386520124620800)

    async def _channel(_bot):
        return channel

    monkeypatch.setattr("functions.owner_notify.get_owner_notify_channel", _channel)
    embed = discord.Embed(title="Added to a Discord server")
    ok = await post_owner_notice(SimpleNamespace(), embed=embed)
    assert ok is True
    assert channel.kwargs is not None
    assert channel.kwargs["content"] == "<@464386520124620800>"
    assert channel.kwargs["embed"] is embed
    mentions = channel.kwargs["allowed_mentions"]
    assert mentions.everyone is False
    assert mentions.roles is False


@pytest.mark.asyncio
async def test_post_owner_notice_restart_includes_message(monkeypatch):
    channel = _Channel()
    monkeypatch.setattr(config, "RESTART_NOTIFY_USER_ID", 42)

    async def _channel(_bot):
        return channel

    monkeypatch.setattr("functions.owner_notify.get_owner_notify_channel", _channel)
    ok = await post_owner_notice(SimpleNamespace(), content="Sir-5rM8 is online after restart/redeploy.")
    assert ok is True
    assert channel.kwargs is not None
    assert channel.kwargs["content"].startswith("<@42> ")
    assert "online after restart/redeploy" in channel.kwargs["content"]
    assert "embed" not in channel.kwargs


@pytest.mark.asyncio
async def test_post_owner_notice_skips_when_user_disabled(monkeypatch):
    channel = _Channel()
    monkeypatch.setattr(config, "RESTART_NOTIFY_USER_ID", None)

    async def _channel(_bot):
        return channel

    monkeypatch.setattr("functions.owner_notify.get_owner_notify_channel", _channel)
    ok = await post_owner_notice(SimpleNamespace(), content="hello")
    assert ok is False
    assert channel.kwargs is None


class _NotifyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id
        self.sent: str | None = None

    async def send(self, content: str) -> None:
        self.sent = content


@pytest.mark.asyncio
async def test_notify_restart_dms_user(monkeypatch):
    user = _NotifyUser(42)
    monkeypatch.setattr(config, "RESTART_NOTIFY_USER_ID", 42)

    class _Bot:
        def get_user(self, user_id: int):
            return user if user_id == 42 else None

        async def fetch_user(self, user_id: int):
            return user if user_id == 42 else None

    await notify_restart(_Bot(), "Sir-5rM8 is online after restart/redeploy.")
    assert user.sent == "Sir-5rM8 is online after restart/redeploy."
