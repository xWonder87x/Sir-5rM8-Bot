"""Async command paths should delegate blocking storage work to asyncio.to_thread."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.community import karma as karma_mod
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
async def test_karma_give_uses_to_thread() -> None:
    bot = MagicMock()
    cog = karma_mod.Karma(bot)
    interaction = _interaction()
    member = MagicMock()
    member.id = 200
    member.display_name = "Receiver"
    member.mention = "<@200>"

    with patch.object(karma_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.side_effect = [
            {"cooldown_hours": 24, "history_limit": 10},
            None,
            5,
        ]
        await cog.karma.callback(cog, interaction, member, "helped")
        assert mock_tt.await_count == 3
        mock_tt.assert_any_await(karma_mod.functions.get_karma_settings)
        mock_tt.assert_any_await(
            karma_mod.functions.karma_get_cooldown, "100", "200"
        )
        mock_tt.assert_any_await(
            karma_mod.functions.karma_add,
            "100",
            "200",
            "Giver",
            reason="helped",
        )
        interaction.response.defer.assert_awaited()
        interaction.followup.send.assert_awaited()


@pytest.mark.asyncio
async def test_karma_check_uses_to_thread() -> None:
    bot = MagicMock()
    cog = karma_mod.Karma(bot)
    interaction = _interaction()
    action = MagicMock()
    action.value = "check"

    with patch.object(karma_mod.asyncio, "to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = 3
        await cog.manage_karma.callback(cog, interaction, action, None)
        mock_tt.assert_awaited_once_with(karma_mod.functions.karma_get_balance, "100")
        interaction.response.defer.assert_awaited()


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
