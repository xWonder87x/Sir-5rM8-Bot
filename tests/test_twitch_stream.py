"""Offline tests for the Twitch watchlist command and persistence."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.integrations import twitch_stream as twitch


def test_parse_twitch_logins_accepts_separators_and_normalizes() -> None:
    valid, invalid = twitch.parse_twitch_logins(" Sh0tTek, gingarella\nnew_name ")

    assert valid == ["sh0ttek", "gingarella", "new_name"]
    assert invalid == []


def test_parse_twitch_logins_rejects_bad_names_and_caps_batch() -> None:
    names = " ".join(["valid_name"] * 2 + ["bad-name", "x" * 26] + [f"user{i}" for i in range(30)])

    valid, invalid = twitch.parse_twitch_logins(names)

    assert len(valid) == twitch.MAX_STREAMERS_PER_BATCH
    assert "bad-name" in invalid
    assert "x" * 26 in invalid
    assert "user29" in invalid


def test_streamer_authorization_requires_administrator() -> None:
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.guild_permissions.administrator = True

    assert twitch._can_manage_streamers(interaction) is True


@pytest.mark.asyncio
async def test_streamer_logins_merges_defaults_and_persisted_once() -> None:
    cog = twitch.TwitchStream.__new__(twitch.TwitchStream)
    cog._streamers_ready = False
    cog.streamers = []
    cog.ping_role_id = None
    cog.discord_channel_id = None

    with patch.object(twitch, "TWITCH_CHANNELS", ["Default", "shared"]), patch.object(
        twitch.blob_state, "cache_get", return_value={}
    ), patch.object(
        twitch.blob_state, "cache_replace"
    ) as replace, patch.object(
        twitch.db, "get_twitch_watchlist", return_value=["shared", "Persisted"]
    ) as getter:
        assert await cog._streamer_logins() == ["default", "shared", "persisted"]
        assert await cog._streamer_logins() == ["default", "shared", "persisted"]
        getter.assert_called_once_with()
        replace.assert_called_once()


@pytest.mark.asyncio
async def test_add_streamers_requires_admin_or_allowed_role() -> None:
    cog = twitch.TwitchStream.__new__(twitch.TwitchStream)
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.guild_permissions.administrator = False
    interaction.user.roles = []
    interaction.response.send_message = AsyncMock()

    with patch.object(twitch, "_can_manage_streamers", return_value=False):
        await twitch.TwitchStream.streamers_add.callback(cog, interaction, "alice")

    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_add_streamers_persists_and_updates_memory() -> None:
    cog = twitch.TwitchStream.__new__(twitch.TwitchStream)
    cog._streamers_ready = True
    cog.streamers = ["default"]
    cog.ping_role_id = None
    cog.discord_channel_id = None
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    with patch.object(twitch, "_can_manage_streamers", return_value=True), patch.object(
        twitch.db,
        "add_twitch_watchlist",
        return_value=(["alice"], ["default"]),
    ) as persist, patch.object(twitch.blob_state, "cache_replace") as replace:
        await twitch.TwitchStream.streamers_add.callback(cog, interaction, "alice default")

    persist.assert_called_once_with(["alice"])
    assert cog.streamers == ["default", "alice"]
    replace.assert_called_once()
    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    message = interaction.followup.send.await_args.args[0]
    assert "Added: alice" in message
    assert "Already present: default" in message
