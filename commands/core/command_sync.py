"""
Slash command sync helpers.

Discord rate-limits application command updates. Do not call sync on every
on_ready reconnect — only after cogs load or when an admin explicitly requests it.

Sync strategy: **global only**. We also clear guild-scoped commands for configured
guild IDs so Discord does not show duplicate slash entries.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord

from config import SLASH_SYNC_GUILD_IDS

if TYPE_CHECKING:
    from discord.ext.commands import Bot

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    guild_scope_cleared: int | None
    global_count: int | None
    command_names: list[str]
    guild_error: Exception | None
    global_error: Exception | None

    @property
    def ok(self) -> bool:
        return self.global_error is None


async def sync_application_commands(bot: Bot) -> SyncResult:
    """Clear stale guild-scoped commands where configured, then global sync."""
    guild_err: Exception | None = None
    guild_scope_cleared: int | None = None
    global_count: int | None = None
    global_err: Exception | None = None
    names: list[str] = []

    if SLASH_SYNC_GUILD_IDS:
        guild_scope_cleared = 0
        for guild_id in SLASH_SYNC_GUILD_IDS:
            try:
                guild = discord.Object(id=guild_id)
                bot.tree.clear_commands(guild=guild)
                await bot.tree.sync(guild=guild)
                guild_scope_cleared += 1
                logger.info(
                    "Cleared guild-scoped slash commands for guild %s",
                    guild_id,
                )
            except Exception as e:
                guild_err = e
                logger.exception(
                    "Could not clear guild-scoped commands for %s: %s",
                    guild_id,
                    e,
                )
            await asyncio.sleep(2.0)

    try:
        synced = await bot.tree.sync()
        global_count = len(synced)
        names = sorted(cmd.name for cmd in synced)
        logger.info(
            "Global slash sync: %s command(s): %s",
            global_count,
            ", ".join(names),
        )
    except Exception as e:
        global_err = e
        logger.exception("Global command sync failed: %s", e)

    return SyncResult(
        guild_scope_cleared,
        global_count,
        names,
        guild_err,
        global_err,
    )
