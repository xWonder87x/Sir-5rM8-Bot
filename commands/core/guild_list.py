"""Permanent embed listing Discord guilds the bot is in (replaces /servers)."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

import config
from commands.common.sticky import StickyMessage
from functions.owner_notify import get_owner_notify_channel, notify_guild_join

logger = logging.getLogger(__name__)

EMBED_TITLE_PREFIX = "Servers ("
_DESC_MAX = 4096


def _guild_sort_key(guild: discord.Guild) -> str:
    return (guild.name or "").lower()


def build_guild_list_embed(guilds: list[discord.Guild]) -> discord.Embed:
    ordered = sorted(guilds, key=_guild_sort_key)
    count = len(ordered)
    lines = [f"**{guild.name}** — `{guild.id}`" for guild in ordered]
    if not lines:
        description = "No servers."
    else:
        description = "\n".join(lines)
        if len(description) > _DESC_MAX:
            kept: list[str] = []
            used = 0
            suffix = "\n…and 999 more"
            budget = _DESC_MAX - len(suffix)
            for line in lines:
                extra = len(line) + (1 if kept else 0)
                if used + extra > budget:
                    break
                kept.append(line)
                used += extra
            omitted = count - len(kept)
            description = "\n".join(kept) + f"\n…and {omitted} more"
    embed = discord.Embed(
        title=f"Servers ({count})",
        description=description,
        colour=discord.Colour.pink(),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_footer(text="Updates hourly and when the bot joins a server")
    return embed


def is_guild_list_sticky(msg: discord.Message, bot_id: int) -> bool:
    return (
        msg.author.id == bot_id
        and bool(msg.embeds)
        and (msg.embeds[0].title or "").startswith(EMBED_TITLE_PREFIX)
    )


async def _pin_guild_list(msg: discord.Message) -> None:
    if getattr(msg, "pinned", False):
        return
    try:
        await msg.pin(reason="Permanent guild list")
    except (discord.Forbidden, discord.HTTPException):
        pass


class GuildList(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._lock = asyncio.Lock()
        self._sticky: StickyMessage | None = None

    async def cog_load(self) -> None:
        if os.environ.get("EXTENSION_VERIFY"):
            return
        if not config.GUILD_LIST_CHANNEL_ID:
            logger.warning(
                "GUILD_LIST_CHANNEL_ID is unset; guild list embed is disabled"
            )
            return
        if not self.refresh_guild_list.is_running():
            self.refresh_guild_list.start()

    def cog_unload(self) -> None:
        self.refresh_guild_list.cancel()

    async def _resolve_channel(self) -> discord.TextChannel | None:
        return await get_owner_notify_channel(self.bot)

    async def _load_sticky(self) -> StickyMessage:
        if self._sticky is None:
            self._sticky = await asyncio.to_thread(
                StickyMessage,
                self.bot,
                state_path=config.DATA_DIR / "guild_list_message.json",
                matcher=is_guild_list_sticky,
                log_label="guild_list",
                pin=_pin_guild_list,
            )
        return self._sticky

    async def _refresh(self) -> None:
        async with self._lock:
            channel = await self._resolve_channel()
            if channel is None:
                return
            embed = build_guild_list_embed(list(self.bot.guilds))
            sticky = await self._load_sticky()
            await sticky.ensure(channel, embed)

    @tasks.loop(hours=1)
    async def refresh_guild_list(self) -> None:
        try:
            await self._refresh()
        except Exception:
            logger.exception("Guild list refresh failed")

    @refresh_guild_list.before_loop
    async def before_refresh_guild_list(self) -> None:
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        if not self.refresh_guild_list.is_running():
            return
        try:
            await self._refresh()
        except Exception:
            logger.exception("Guild list refresh after join failed")
        try:
            await notify_guild_join(self.bot, guild)
        except Exception:
            logger.exception("Guild join owner notice failed")

    @commands.Cog.listener()
    async def on_guild_remove(self, _guild: discord.Guild) -> None:
        if not self.refresh_guild_list.is_running():
            return
        try:
            await self._refresh()
        except Exception:
            logger.exception("Guild list refresh after leave failed")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GuildList(bot))
