"""Twitch go-live notifications and the /streamers command group."""
from __future__ import annotations

import asyncio
import logging
import os
import re

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
from functions import blob_state

logger = logging.getLogger(__name__)

TWITCH_CHANNELS = getattr(config, "TWITCH_CHANNELS", [])
TWITCH_LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{1,25}$")
MAX_STREAMERS_PER_BATCH = 25
POLL_INTERVAL_MINUTES = max(1, int(getattr(config, "TWITCH_POLL_INTERVAL_MINUTES", 10)))
WATCHLIST_KEY = blob_state.TWITCH_WATCHLIST_KEY
PINGED_KEY = blob_state.TWITCH_PINGED_KEY


def parse_twitch_logins(value: str) -> tuple[list[str], list[str]]:
    """Parse comma/space-separated Twitch logins into valid and invalid names."""
    valid: list[str] = []
    invalid: list[str] = []
    for token in re.split(r"[\s,]+", value or ""):
        if not token:
            continue
        normalized = token.lower()
        if TWITCH_LOGIN_RE.fullmatch(token) and len(valid) < MAX_STREAMERS_PER_BATCH:
            if normalized not in valid:
                valid.append(normalized)
        else:
            invalid.append(token)
    return valid, invalid


def _can_manage_streamers(interaction: discord.Interaction) -> bool:
    member = interaction.user
    return bool(
        interaction.guild
        and isinstance(member, discord.Member)
        and member.guild_permissions.administrator
    )


def _watchlist_state(cog: "TwitchStream") -> dict:
    state = blob_state.cache_get(WATCHLIST_KEY)
    if not isinstance(state, dict):
        state = {}
    state.setdefault("logins", list(TWITCH_CHANNELS))
    state.setdefault("ping_role_id", config.TWITCH_PING_ROLE_ID)
    state.setdefault("discord_channel_id", config.TWITCH_DISCORD_CHANNEL_ID)
    return state


async def _get_twitch_token() -> str | None:
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("access_token")
    except (aiohttp.ClientError, KeyError, TypeError):
        logger.warning("Twitch token request failed")
        return None


async def _get_stream_info(login: str) -> dict | None:
    token = await _get_twitch_token()
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    if not token or not client_id:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.twitch.tv/helix/streams",
                params={"user_login": login},
                headers={"Client-ID": client_id, "Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response.raise_for_status()
                data = await response.json()
                streams = data.get("data", [])
                return streams[0] if streams else None
    except (aiohttp.ClientError, KeyError, TypeError):
        logger.warning("Twitch stream lookup failed for %s", login)
        return None


class StreamNotifyView(discord.ui.View):
    """Buttons for adding or removing the configured notification role."""

    def __init__(self, role_id: int, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.role_id = role_id

    @discord.ui.button(
        label="Notify me when streamers go live",
        style=discord.ButtonStyle.primary,
        custom_id="s5_twitch_notify",
    )
    async def notify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, add=True)

    @discord.ui.button(
        label="Remove notifications",
        style=discord.ButtonStyle.secondary,
        custom_id="s5_twitch_notify_remove",
    )
    async def remove(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, add=False)

    async def _toggle(self, interaction: discord.Interaction, *, add: bool) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        member = interaction.user
        if role is None or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "I couldn't find the notification role or your member record.",
                ephemeral=True,
            )
            return
        try:
            if add:
                await member.add_roles(role, reason="Twitch stream notifications")
                message = "You will now get Twitch go-live notifications."
            else:
                await member.remove_roles(role, reason="Twitch stream notifications")
                message = "You will no longer get Twitch go-live notifications."
            await interaction.response.send_message(message, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to manage that role.", ephemeral=True
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "Discord rejected the role update. Please try again.", ephemeral=True
            )


class TwitchStream(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready = False
        state = _watchlist_state(self)
        self.streamers = [str(x).lower() for x in state.get("logins", []) if x]
        self.ping_role_id = state.get("ping_role_id")
        self.discord_channel_id = state.get("discord_channel_id")
        if self.ping_role_id:
            bot.add_view(StreamNotifyView(int(self.ping_role_id)))
        if not os.environ.get("EXTENSION_VERIFY"):
            self.check_stream_task.change_interval(minutes=POLL_INTERVAL_MINUTES)
            self.check_stream_task.start()

    def cog_unload(self) -> None:
        self.check_stream_task.cancel()

    def _save_state(self) -> None:
        blob_state.cache_replace(
            WATCHLIST_KEY,
            {
                "logins": self.streamers,
                "ping_role_id": self.ping_role_id,
                "discord_channel_id": self.discord_channel_id,
            },
            flush=True,
        )

    streamers_group = app_commands.Group(
        name="streamers", description="Manage Twitch go-live notifications"
    )

    @streamers_group.command(name="add", description="Add Twitch logins to the watchlist")
    @app_commands.describe(streamers="Comma- or space-separated Twitch login names")
    async def streamers_add(self, interaction: discord.Interaction, streamers: str):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.", ephemeral=True
            )
            return
        valid, invalid = parse_twitch_logins(streamers)
        if not valid:
            await interaction.response.send_message(
                "No valid Twitch login names were provided.", ephemeral=True
            )
            return
        current = self.streamers
        already = [login for login in valid if login in current]
        added = [login for login in valid if login not in current]
        current.extend(added)
        self._save_state()
        parts = []
        if added:
            parts.append(f"Added: {', '.join(added)}")
        if already:
            parts.append(f"Already present: {', '.join(already)}")
        if invalid:
            parts.append(f"Invalid: {', '.join(invalid)}")
        await interaction.response.send_message(". ".join(parts) + ".", ephemeral=True)

    @streamers_group.command(name="list", description="List Twitch logins on the watchlist")
    async def streamers_list(self, interaction: discord.Interaction):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.", ephemeral=True
            )
            return
        role = (
            interaction.guild.get_role(int(self.ping_role_id))
            if interaction.guild and self.ping_role_id
            else None
        )
        channel = (
            interaction.guild.get_channel(int(self.discord_channel_id))
            if interaction.guild and self.discord_channel_id
            else None
        )
        body = ", ".join(f"`{login}`" for login in self.streamers) or "The watchlist is empty."
        await interaction.response.send_message(
            f"Streamers ({len(self.streamers)}): {body}\n"
            f"Ping role: {role.mention if role else 'none'}\n"
            f"Ping channel: {channel.mention if channel else 'configured default / none'}",
            ephemeral=True,
        )

    @streamers_group.command(name="remove", description="Remove Twitch logins from the watchlist")
    @app_commands.describe(streamers="Comma- or space-separated Twitch login names")
    async def streamers_remove(self, interaction: discord.Interaction, streamers: str):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.", ephemeral=True
            )
            return
        valid, invalid = parse_twitch_logins(streamers)
        removed = [login for login in valid if login in self.streamers and login not in TWITCH_CHANNELS]
        protected = [login for login in valid if login in TWITCH_CHANNELS]
        missing = [login for login in valid if login not in self.streamers]
        self.streamers[:] = [login for login in self.streamers if login not in removed]
        if removed:
            self._save_state()
        parts = []
        if removed:
            parts.append(f"Removed: {', '.join(removed)}")
        if protected:
            parts.append(f"Configured defaults cannot be removed: {', '.join(protected)}")
        if missing:
            parts.append(f"Not present: {', '.join(missing)}")
        if invalid:
            parts.append(f"Invalid: {', '.join(invalid)}")
        await interaction.response.send_message(". ".join(parts) + ".", ephemeral=True)

    @streamers_group.command(name="setup", description="Choose the alert role and channel")
    @app_commands.describe(
        role="The Discord role to mention", channel="The text channel for go-live alerts"
    )
    async def streamers_setup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        channel: discord.TextChannel,
    ):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.", ephemeral=True
            )
            return
        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "That role cannot be used for Twitch alerts.", ephemeral=True
            )
            return
        if interaction.guild is None or channel.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                "That channel is not in this server.", ephemeral=True
            )
            return
        bot_member = interaction.guild.me
        if bot_member is None or role >= bot_member.top_role:
            await interaction.response.send_message(
                "I cannot use a role at or above my highest role.", ephemeral=True
            )
            return
        self.ping_role_id = role.id
        self.discord_channel_id = channel.id
        self._save_state()
        await interaction.response.send_message(
            f"Twitch alerts will ping {role.mention} in {channel.mention}.",
            ephemeral=True,
        )

    async def _streamer_logins(self) -> list[str]:
        if not self._ready:
            state = _watchlist_state(self)
            self.streamers = list(dict.fromkeys(
                str(login).lower() for login in state.get("logins", []) if login
            ))
            self.ping_role_id = state.get("ping_role_id")
            self.discord_channel_id = state.get("discord_channel_id")
            self._ready = True
        return self.streamers

    async def _pinged_map(self) -> dict:
        state = blob_state.cache_get(PINGED_KEY)
        return state if isinstance(state, dict) else {}

    @tasks.loop(minutes=10)
    async def check_stream_task(self):
        streamers = await self._streamer_logins()
        if not streamers or not self.discord_channel_id:
            return
        channel = self.bot.get_channel(int(self.discord_channel_id))
        if channel is None or channel.type != discord.ChannelType.text:
            return
        pinged = await self._pinged_map()
        for login in streamers:
            stream = await _get_stream_info(login)
            if not stream or not stream.get("id"):
                continue
            stream_id = str(stream["id"])
            if pinged.get(login) == stream_id:
                continue
            title = stream.get("title", "Live")
            game = stream.get("game_name") or "Unknown"
            content = (
                f"<@&{self.ping_role_id}> **{login}** is now live on Twitch!\n\n"
                f"**{title}**\n{game} | https://twitch.tv/{login}"
            ) if self.ping_role_id else (
                f"**{login}** is now live on Twitch!\n\n"
                f"**{title}**\n{game} | https://twitch.tv/{login}"
            )
            view = StreamNotifyView(int(self.ping_role_id), timeout=None) if self.ping_role_id else None
            try:
                await channel.send(content, view=view)
                pinged[login] = stream_id
                blob_state.cache_replace(PINGED_KEY, pinged, flush=True)
            except (discord.Forbidden, discord.HTTPException):
                logger.warning("Twitch: failed to send ping for %s", login)

    @check_stream_task.before_loop
    async def before_check_stream_task(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(TwitchStream(bot))
