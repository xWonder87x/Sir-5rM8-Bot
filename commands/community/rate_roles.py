"""Persistent Subscribe / Unsubscribe buttons for the ASA rates role."""
from __future__ import annotations

import asyncio
import logging

import discord

import config
import functions

logger = logging.getLogger(__name__)

SUBSCRIBE_ID = "s5rate:sub"
UNSUBSCRIBE_ID = "s5rate:unsub"


def build_rates_embed(rate_data: dict) -> discord.Embed:
    emb = discord.Embed(
        title="ASA Official Server Rates",
        description="",
        colour=discord.Colour.pink(),
    )
    emb.set_thumbnail(url=config.THUMBNAIL_URL)
    for emoji, label, key in config.RATE_DISPLAY:
        value = rate_data.get(key, "?")
        emb.add_field(name=f"**{emoji} `{value}x` {label}**", value="", inline=False)
    return emb


async def _member_for(interaction: discord.Interaction) -> discord.Member | None:
    if interaction.guild is None:
        return None
    user = interaction.user
    if isinstance(user, discord.Member):
        return user
    try:
        return await interaction.guild.fetch_member(user.id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def toggle_rate_role(interaction: discord.Interaction, *, subscribe: bool) -> None:
    if interaction.guild is None:
        await interaction.response.send_message("Use this in a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    member = await _member_for(interaction)
    if member is None:
        await interaction.followup.send("I couldn't resolve your member record in this server.", ephemeral=True)
        return

    rn = await asyncio.to_thread(functions.get_server_channel, str(interaction.guild.id))
    if not rn:
        await interaction.followup.send(
            "This server has no rate notification role. An admin can set one with `/set_rate_channel`.",
            ephemeral=True,
        )
        return

    try:
        role_id = int(rn["role_id"])
    except (KeyError, TypeError, ValueError):
        await interaction.followup.send(
            "The rate role config is invalid. Ask an admin to run `/set_rate_channel` again.",
            ephemeral=True,
        )
        return

    role = interaction.guild.get_role(role_id)
    if role is None:
        await interaction.followup.send(
            "The rate role no longer exists. Ask an admin to run `/set_rate_channel` again.",
            ephemeral=True,
        )
        return

    me = interaction.guild.me
    if me is None or not me.guild_permissions.manage_roles:
        await interaction.followup.send("I need the **Manage Roles** permission to do that.", ephemeral=True)
        return
    if not role.is_assignable():
        await interaction.followup.send(
            "I can't assign that role. Move my role above it, and don't use @everyone or a managed role.",
            ephemeral=True,
        )
        return

    try:
        if subscribe:
            if role in member.roles:
                await interaction.followup.send("You're already subscribed.", ephemeral=True)
                return
            await member.add_roles(role, reason="Rate notification subscribe")
            await interaction.followup.send(
                f"Subscribed — you'll be pinged as {role.mention} when official rates change.",
                ephemeral=True,
            )
            return
        if role not in member.roles:
            await interaction.followup.send("You're not subscribed.", ephemeral=True)
            return
        await member.remove_roles(role, reason="Rate notification unsubscribe")
        await interaction.followup.send("Unsubscribed — you won't be pinged for rate changes.", ephemeral=True)
    except discord.Forbidden:
        logger.warning("Forbidden toggling rate role %s in guild %s", role.id, interaction.guild.id)
        await interaction.followup.send("I don't have permission to change that role.", ephemeral=True)
    except discord.HTTPException as exc:
        logger.warning("Failed toggling rate role %s: %s", role.id, exc)
        await interaction.followup.send("Couldn't update your role. Please try again.", ephemeral=True)


class RateRoleView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Subscribe", style=discord.ButtonStyle.success, custom_id=SUBSCRIBE_ID)
    async def subscribe(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await toggle_rate_role(interaction, subscribe=True)

    @discord.ui.button(label="Unsubscribe", style=discord.ButtonStyle.danger, custom_id=UNSUBSCRIBE_ID)
    async def unsubscribe(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await toggle_rate_role(interaction, subscribe=False)
