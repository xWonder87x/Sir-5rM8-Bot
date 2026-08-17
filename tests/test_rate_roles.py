from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from commands.community.rate_roles import (
    SUBSCRIBE_ID,
    UNSUBSCRIBE_ID,
    RateRoleView,
    build_rates_embed,
    toggle_rate_role,
)


def test_build_rates_embed_lists_display_keys():
    data = {
        "XPMultiplier": "2",
        "HarvestAmountMultiplier": "3",
        "TamingSpeedMultiplier": "4",
    }
    embed = build_rates_embed(data)
    names = [field.name for field in embed.fields]
    assert embed.title == "ASA Official Server Rates"
    assert any("`2x` EXP" in n for n in names)
    assert any("`3x` Harvesting" in n for n in names)


@pytest.mark.asyncio
async def test_rate_role_view_buttons():
    view = RateRoleView()
    labels = {item.label: (item.style, item.custom_id) for item in view.children}
    assert labels["Subscribe"] == (discord.ButtonStyle.success, SUBSCRIBE_ID)
    assert labels["Unsubscribe"] == (discord.ButtonStyle.danger, UNSUBSCRIBE_ID)
    assert view.timeout is None


@pytest.mark.asyncio
async def test_toggle_rate_role_requires_guild() -> None:
    interaction = MagicMock()
    interaction.guild = None
    interaction.response = AsyncMock()
    await toggle_rate_role(interaction, subscribe=True)
    interaction.response.send_message.assert_awaited()
    assert interaction.response.send_message.await_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_toggle_rate_role_subscribes() -> None:
    role = MagicMock(spec=discord.Role)
    role.id = 20
    role.mention = "<@&20>"
    role.is_assignable.return_value = True

    member = MagicMock(spec=discord.Member)
    member.roles = []
    member.add_roles = AsyncMock()

    guild = MagicMock()
    guild.id = 1
    guild.get_role.return_value = role
    guild.me = MagicMock()
    guild.me.guild_permissions.manage_roles = True
    guild.fetch_member = AsyncMock(return_value=member)

    interaction = MagicMock()
    interaction.guild = guild
    interaction.user = MagicMock()  # not a Member
    interaction.user.id = 100
    interaction.response = AsyncMock()
    interaction.followup = AsyncMock()

    with patch("commands.community.rate_roles.asyncio.to_thread", new_callable=AsyncMock) as mock_tt:
        mock_tt.return_value = {"channel_id": "10", "role_id": "20"}
        await toggle_rate_role(interaction, subscribe=True)

    member.add_roles.assert_awaited_once()
    interaction.followup.send.assert_awaited()
    assert "Subscribed" in interaction.followup.send.await_args.args[0]
