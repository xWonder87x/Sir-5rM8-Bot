"""Async command paths should delegate blocking storage work to asyncio.to_thread."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.community import ark_notifications as ark_mod
from commands.core import admin as admin_mod


def _interaction(*, guild: bool = True, admin: bool = False) -> MagicMock:
    interaction = MagicMock()
    interaction.guild = MagicMock() if guild else None
    if interaction.guild is not None:
        interaction.guild.id = 1
        interaction.guild.get_channel = MagicMock(return_value=None)
        interaction.guild.get_role = MagicMock(return_value=None)
    interaction.user = MagicMock()
    interaction.user.id = 100
    interaction.user.display_name = "Giver"
    interaction.user.guild_permissions = MagicMock()
    interaction.user.guild_permissions.administrator = admin
    interaction.response = AsyncMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.followup = AsyncMock()
    return interaction


@pytest.mark.asyncio
async def test_set_rate_channel_uses_to_thread() -> None:
    bot = MagicMock()
    cog = admin_mod.Admin(bot)
    interaction = _interaction()
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 10
    channel.mention = "#rates"
    channel.send = AsyncMock()
    role = MagicMock(spec=discord.Role)
    role.id = 20

    with patch.object(admin_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = None
        await cog.set_rate_channel.callback(cog, interaction, channel, role)
        mock_tt.assert_awaited_once_with(
            admin_mod.functions.add_server_channel, "1", "10", "20"
        )
        interaction.response.defer.assert_awaited()


@pytest.mark.asyncio
async def test_rate_channel_status_uses_to_thread() -> None:
    bot = MagicMock()
    cog = admin_mod.Admin(bot)
    interaction = _interaction()

    with patch.object(admin_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = None
        await cog.rate_channel_status.callback(cog, interaction)
        mock_tt.assert_awaited_once_with(admin_mod.functions.get_server_channel, "1")


@pytest.mark.asyncio
async def test_clear_rate_channel_uses_to_thread() -> None:
    bot = MagicMock()
    cog = admin_mod.Admin(bot)
    interaction = _interaction()

    with patch.object(admin_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = True
        await cog.clear_rate_channel.callback(cog, interaction)
        mock_tt.assert_awaited_once_with(admin_mod.functions.clear_server_channel, "1")


@pytest.mark.asyncio
async def test_arknotifications_uses_to_thread() -> None:
    bot = MagicMock()
    cog = ark_mod.ArkNotifications(bot)
    interaction = _interaction()

    with patch.object(ark_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = None
        await cog.arknotifications.callback(cog, interaction)
        mock_tt.assert_awaited_once_with(ark_mod.notice_cache.get_ark_notification, "1")
        interaction.response.defer.assert_awaited()
        interaction.followup.send.assert_awaited()


@pytest.mark.asyncio
async def test_post_ark_notice_skips_execsave() -> None:
    channel = MagicMock()
    channel.send = AsyncMock()
    with patch.object(ark_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        result = await ark_mod.post_ark_notice(
            channel, "execsave", guild_id="1", last_message_id="10"
        )
    assert result == "10"
    channel.send.assert_not_called()
    mock_tt.assert_not_awaited()


@pytest.mark.asyncio
async def test_post_ark_notice_replaces_previous_countdown() -> None:
    old = MagicMock()
    old.delete = AsyncMock()
    sent = MagicMock()
    sent.id = 20
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=old)
    channel.send = AsyncMock(return_value=sent)
    with patch.object(ark_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        result = await ark_mod.post_ark_notice(
            channel,
            "Servers restart in 5 minutes",
            guild_id="1",
            last_message_id="10",
        )
    assert result == "20"
    channel.fetch_message.assert_awaited_once_with(10)
    old.delete.assert_awaited_once()
    channel.send.assert_awaited()
    mock_tt.assert_awaited_once_with(
        ark_mod.notice_cache.set_ark_notice_last_message, "1", "20"
    )


@pytest.mark.asyncio
async def test_post_ark_notice_replaces_previous_removal() -> None:
    old = MagicMock()
    old.delete = AsyncMock()
    sent = MagicMock()
    sent.id = 21
    channel = MagicMock()
    channel.fetch_message = AsyncMock(return_value=old)
    channel.send = AsyncMock(return_value=sent)
    with patch.object(ark_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        result = await ark_mod.post_ark_notice(
            channel,
            "The following servers will be removed from the official list",
            guild_id="1",
            last_message_id="10",
        )
    assert result == "21"
    channel.fetch_message.assert_awaited_once_with(10)
    old.delete.assert_awaited_once()
    channel.send.assert_awaited()
    embed = channel.send.await_args.kwargs["embed"]
    assert embed.title == "Official ARK Server Removal"
    mock_tt.assert_awaited_once_with(
        ark_mod.notice_cache.set_ark_notice_last_message, "1", "21"
    )
