"""
Twitch stream notifications: ping in Discord when the streamer goes live.
Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in .env.

Pinged stream ids live in memory and flush to STATE_BUCKET (not Neon polls).
Watchlist logins persist in the database and are mirrored to STATE_BUCKET.
"""
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
import db
from functions import blob_state

logger = logging.getLogger(__name__)

TWITCH_CHANNELS = getattr(config, "TWITCH_CHANNELS", None) or []
TWITCH_LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{1,25}$")
MAX_STREAMERS_PER_BATCH = 25
DISCORD_CHANNEL_ID = getattr(config, "TWITCH_DISCORD_CHANNEL_ID", None)
PING_ROLE_ID = getattr(config, "TWITCH_PING_ROLE_ID", None)
POLL_INTERVAL_MINUTES = int(getattr(config, "TWITCH_POLL_INTERVAL_MINUTES", 10) or 10)


def parse_twitch_logins(value: str) -> tuple[list[str], list[str]]:
    """Parse comma/space-separated Twitch logins into valid and invalid names."""
    tokens = [token for token in re.split(r"[\s,]+", value or "") if token]
    valid: list[str] = []
    invalid: list[str] = []
    for token in tokens:
        normalized = token.lower()
        if TWITCH_LOGIN_RE.fullmatch(token) and normalized in valid:
            continue
        if TWITCH_LOGIN_RE.fullmatch(token) and len(valid) < MAX_STREAMERS_PER_BATCH:
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


def _ensure_pinged_cache() -> dict:
    """Load Twitch ping map once: bucket first, else one-shot Neon migrate."""
    data = blob_state.cache_get(blob_state.TWITCH_PINGED_KEY)
    if data:
        return data
    try:
        neon = db.get_twitch_pinged()
    except Exception as e:
        logger.warning("Twitch: Neon migrate read failed: %s", e)
        neon = {}
    if neon:
        blob_state.cache_replace(blob_state.TWITCH_PINGED_KEY, neon, flush=True)
        logger.info(
            "Twitch: migrated %d pinged login(s) from Neon to state bucket",
            len(neon),
        )
        return dict(neon)
    return {}


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
            ) as r:
                r.raise_for_status()
                data = await r.json()
                return data.get("access_token")
    except (aiohttp.ClientError, KeyError) as e:
        logger.warning("Twitch: failed to get token: %s", e)
        return None


class StreamNotifyButton(discord.ui.View):
    """Button to subscribe to stream notifications (adds the ping role)."""

    def __init__(self, role_id: int, timeout: float | None = None):
        super().__init__(timeout=timeout)
        self.role_id = role_id

    @discord.ui.button(
        label="Notify me when streamers go live",
        style=discord.ButtonStyle.primary,
        custom_id="twitch_notify",
    )
    async def notify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild is None:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                "The notification role could not be found.", ephemeral=True
            )
            return
        member = interaction.user
        if isinstance(member, discord.User):
            member = interaction.guild.get_member(member.id)
        if not member:
            await interaction.response.send_message(
                "Could not find you in this server.", ephemeral=True
            )
            return
        if role in member.roles:
            await interaction.response.send_message(
                "You already have the stream notification role!", ephemeral=True
            )
            return
        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                "You will now get notified when streamers go live!", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to add that role.", ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Something went wrong: {e}", ephemeral=True)

    @discord.ui.button(
        emoji="🔕",
        style=discord.ButtonStyle.secondary,
        custom_id="twitch_notify_remove",
    )
    async def remove_notify_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.guild is None:
            await interaction.response.send_message("Use this in a server.", ephemeral=True)
            return
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message(
                "The notification role could not be found.", ephemeral=True
            )
            return
        member = interaction.user
        if isinstance(member, discord.User):
            member = interaction.guild.get_member(member.id)
        if not member:
            await interaction.response.send_message(
                "Could not find you in this server.", ephemeral=True
            )
            return
        if role not in member.roles:
            await interaction.response.send_message(
                "You do not have the stream notification role.", ephemeral=True
            )
            return
        try:
            await member.remove_roles(role)
            await interaction.response.send_message(
                "You will no longer get notified when streamers go live.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to remove that role.", ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Something went wrong: {e}", ephemeral=True)


async def _get_stream_info(channel_login: str) -> dict | None:
    token = await _get_twitch_token()
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    if not token or not client_id:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.twitch.tv/helix/streams",
                params={"user_login": channel_login},
                headers={
                    "Client-ID": client_id,
                    "Authorization": f"Bearer {token}",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                r.raise_for_status()
                data = await r.json()
                streams = data.get("data", [])
                return streams[0] if streams else None
    except (aiohttp.ClientError, KeyError) as e:
        logger.warning("Twitch: failed to get stream: %s", e)
        return None


class TwitchStream(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._pinged_ready = False
        self._streamers_ready = False
        self.streamers: list[str] = []
        self.ping_role_id = PING_ROLE_ID
        self.discord_channel_id = DISCORD_CHANNEL_ID
        if PING_ROLE_ID:
            bot.add_view(StreamNotifyButton(PING_ROLE_ID))
        if not os.environ.get("EXTENSION_VERIFY"):
            self.check_stream_task.change_interval(minutes=max(1, POLL_INTERVAL_MINUTES))
            self.check_stream_task.start()

    def cog_unload(self):
        self.check_stream_task.cancel()

    async def _pinged_map(self) -> dict:
        if not self._pinged_ready:
            await asyncio.to_thread(_ensure_pinged_cache)
            self._pinged_ready = True
        return await asyncio.to_thread(
            blob_state.cache_get, blob_state.TWITCH_PINGED_KEY
        )

    async def _streamer_logins(self) -> list[str]:
        if not self._streamers_ready:
            state = await asyncio.to_thread(
                blob_state.cache_get, blob_state.TWITCH_WATCHLIST_KEY
            )
            persisted = state.get("logins") if isinstance(state, dict) else None
            if isinstance(state, dict) and isinstance(state.get("ping_role_id"), int):
                self.ping_role_id = state["ping_role_id"]
            if isinstance(state, dict) and isinstance(state.get("discord_channel_id"), int):
                self.discord_channel_id = state["discord_channel_id"]
            if not isinstance(persisted, list):
                try:
                    persisted = await asyncio.to_thread(db.get_twitch_watchlist)
                except Exception:
                    logger.warning(
                        "Twitch: watchlist table unavailable; using config defaults"
                    )
                    persisted = []
                await asyncio.to_thread(
                    blob_state.cache_replace,
                    blob_state.TWITCH_WATCHLIST_KEY,
                    {
                        "logins": persisted,
                        "ping_role_id": getattr(self, "ping_role_id", PING_ROLE_ID),
                        "discord_channel_id": getattr(
                            self, "discord_channel_id", DISCORD_CHANNEL_ID
                        ),
                    },
                    flush=True,
                )
            self.streamers = list(
                dict.fromkeys(
                    str(login).lower()
                    for login in [*TWITCH_CHANNELS, *persisted]
                    if login
                )
            )
            self._streamers_ready = True
        return self.streamers

    streamers_group = app_commands.Group(
        name="streamers", description="Manage the Twitch go-live watchlist"
    )

    @streamers_group.command(name="add", description="Add Twitch logins to the go-live watchlist")
    @app_commands.describe(streamers="Comma- or space-separated Twitch login names")
    async def streamers_add(self, interaction: discord.Interaction, streamers: str):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return
        valid, invalid = parse_twitch_logins(streamers)
        if not valid:
            detail = f" Invalid names: {', '.join(invalid)}." if invalid else ""
            await interaction.response.send_message(
                f"No valid Twitch login names were provided.{detail}", ephemeral=True
            )
            return
        current = await self._streamer_logins()
        already_present = [login for login in valid if login in current]
        to_add = [login for login in valid if login not in current]
        await interaction.response.defer(ephemeral=True)
        try:
            added, persisted_already = await asyncio.to_thread(
                db.add_twitch_watchlist, to_add
            )
        except Exception:
            logger.exception("Twitch: failed to persist stream watchlist")
            await interaction.followup.send(
                "I couldn't save the Twitch watchlist. Please try again.", ephemeral=True
            )
            return
        already_present.extend(
            login for login in persisted_already if login not in already_present
        )
        current.extend(login for login in added if login not in current)
        await asyncio.to_thread(
            blob_state.cache_replace,
            blob_state.TWITCH_WATCHLIST_KEY,
            {
                "logins": current,
                "ping_role_id": getattr(self, "ping_role_id", PING_ROLE_ID),
                "discord_channel_id": getattr(
                    self, "discord_channel_id", DISCORD_CHANNEL_ID
                ),
            },
            flush=True,
        )
        self._streamers_ready = True
        parts = []
        if added:
            parts.append(f"Added: {', '.join(added)}")
        if already_present:
            parts.append(f"Already present: {', '.join(already_present)}")
        if invalid:
            parts.append(f"Invalid: {', '.join(invalid)}")
        await interaction.followup.send(". ".join(parts) + ".", ephemeral=True)

    @streamers_group.command(name="list", description="List Twitch logins on the go-live watchlist")
    async def streamers_list(self, interaction: discord.Interaction):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return
        current = await self._streamer_logins()
        role = (
            interaction.guild.get_role(self.ping_role_id)
            if self.ping_role_id and interaction.guild
            else None
        )
        role_text = role.mention if role else "none"
        channel = (
            interaction.guild.get_channel(self.discord_channel_id)
            if self.discord_channel_id and interaction.guild
            else None
        )
        channel_text = channel.mention if channel else "configured default / none"
        body = ", ".join(f"`{login}`" for login in current) or "The watchlist is empty."
        await interaction.response.send_message(
            f"Streamers ({len(current)}): {body}\n"
            f"Ping role: {role_text}\nPing channel: {channel_text}",
            ephemeral=True,
        )

    @streamers_group.command(name="remove", description="Remove Twitch logins from the go-live watchlist")
    @app_commands.describe(streamers="Comma- or space-separated Twitch login names")
    async def streamers_remove(self, interaction: discord.Interaction, streamers: str):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return
        valid, invalid = parse_twitch_logins(streamers)
        if not valid:
            await interaction.response.send_message(
                "No valid Twitch login names were provided.", ephemeral=True
            )
            return
        current = await self._streamer_logins()
        removed = [login for login in valid if login in current and login not in TWITCH_CHANNELS]
        protected = [login for login in valid if login in TWITCH_CHANNELS]
        missing = [login for login in valid if login not in current]
        if removed:
            current[:] = [login for login in current if login not in removed]
            await asyncio.to_thread(db.remove_twitch_watchlist, removed)
            await asyncio.to_thread(
                blob_state.cache_replace,
                blob_state.TWITCH_WATCHLIST_KEY,
                {
                    "logins": current,
                    "ping_role_id": getattr(self, "ping_role_id", PING_ROLE_ID),
                    "discord_channel_id": getattr(
                        self, "discord_channel_id", DISCORD_CHANNEL_ID
                    ),
                },
                flush=True,
            )
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

    @streamers_group.command(
        name="setup", description="Choose the role and channel for Twitch go-live alerts"
    )
    @app_commands.describe(
        role="The Discord role to mention",
        channel="The text channel where alerts will be posted",
    )
    async def streamers_setup(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        channel: discord.TextChannel,
    ):
        if not _can_manage_streamers(interaction):
            await interaction.response.send_message(
                "Administrator permission is required.",
                ephemeral=True,
            )
            return
        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "That role cannot be used for Twitch alerts.", ephemeral=True
            )
            return
        bot_member = interaction.guild.me
        if bot_member is None or role >= bot_member.top_role:
            await interaction.response.send_message(
                "I cannot use a role at or above my highest role.", ephemeral=True
            )
            return
        if channel.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                "That channel is not in this server.", ephemeral=True
            )
            return
        await self._streamer_logins()
        self.ping_role_id = role.id
        self.discord_channel_id = channel.id
        await asyncio.to_thread(
            blob_state.cache_replace,
            blob_state.TWITCH_WATCHLIST_KEY,
            {
                "logins": self.streamers,
                "ping_role_id": role.id,
                "discord_channel_id": channel.id,
            },
            flush=True,
        )
        await interaction.response.send_message(
            f"Twitch go-live alerts will now ping {role.mention} in {channel.mention}.",
            ephemeral=True,
        )

    @tasks.loop(minutes=10)
    async def check_stream_task(self):
        try:
            await self.bot.wait_until_ready()
            streamers = await self._streamer_logins()
            if not streamers or not self.discord_channel_id:
                return
            channel = self.bot.get_channel(self.discord_channel_id)
            if not channel or channel.type != discord.ChannelType.text:
                return
            pinged = await self._pinged_map()
            ping = f"<@&{self.ping_role_id}> " if self.ping_role_id else "@here "
            for twitch_login in streamers:
                stream = await _get_stream_info(twitch_login)
                if not stream:
                    continue
                stream_id = stream.get("id")
                if not stream_id:
                    continue
                key = str(twitch_login).lower()
                if pinged.get(key) == stream_id:
                    continue
                title = stream.get("title", "Live")
                game = stream.get("game_name") or "Unknown"
                url = f"https://twitch.tv/{twitch_login}"
                content = (
                    f"{ping}**{twitch_login}** is now live on Twitch!\n\n"
                    f"**{title}**\n{game} | {url}"
                )
                view = discord.ui.View()
                if self.ping_role_id:
                    view = StreamNotifyButton(self.ping_role_id, timeout=None)
                try:
                    await channel.send(content, view=view)
                except (discord.Forbidden, discord.HTTPException) as e:
                    logger.warning("Twitch: failed to send ping for %s: %s", twitch_login, e)
                    continue
                try:
                    await asyncio.to_thread(
                        blob_state.cache_set_item,
                        blob_state.TWITCH_PINGED_KEY,
                        key,
                        stream_id,
                        flush=True,
                    )
                    pinged[key] = stream_id
                    logger.info("Twitch: sent go-live ping for %s", twitch_login)
                except Exception as e:
                    logger.warning("Twitch: failed to persist ping for %s: %s", twitch_login, e)
        except Exception:
            logger.exception("Twitch: check_stream_task failed")

    @check_stream_task.before_loop
    async def before_check_stream_task(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(TwitchStream(bot))
