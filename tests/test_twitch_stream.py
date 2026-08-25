"""Offline tests for the Twitch streamers command group."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.integrations import twitch_stream as twitch


def test_parse_twitch_logins_normalizes_and_limits_batch() -> None:
    valid, invalid = twitch.parse_twitch_logins(" Sh0tTek, gingarella sh0ttek bad-name")

    assert valid == ["sh0ttek", "gingarella"]
    assert invalid == ["bad-name"]


def test_streamer_authorization_requires_administrator() -> None:
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.guild_permissions.administrator = True

    assert twitch._can_manage_streamers(interaction) is True


@pytest.mark.asyncio
async def test_add_streamers_updates_bucket_state() -> None:
    cog = twitch.TwitchStream.__new__(twitch.TwitchStream)
    cog.streamers = ["default"]
    cog.ping_role_id = None
    cog.discord_channel_id = None
    interaction = MagicMock()
    interaction.guild = MagicMock()
    interaction.user = MagicMock()
    interaction.response.send_message = AsyncMock()

    with patch.object(twitch, "_can_manage_streamers", return_value=True):
        await twitch.TwitchStream.streamers_add.callback(cog, interaction, "alice default")

    assert cog.streamers == ["default", "alice"]
    interaction.response.send_message.assert_awaited_once()
    assert "Added: alice" in interaction.response.send_message.await_args.args[0]
    assert "Already present: default" in interaction.response.send_message.await_args.args[0]
