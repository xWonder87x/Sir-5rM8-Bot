import logging

import discord
from discord.ext import commands

from config import SLASH_SYNC_GUILD_IDS

logger = logging.getLogger(__name__)


async def sync_application_commands(bot: commands.Bot) -> None:
    """Clear stale guild-scoped commands where configured, then global sync."""
    for guild_id in SLASH_SYNC_GUILD_IDS:
        guild = discord.Object(id=guild_id)
        bot.tree.clear_commands(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        logger.info("Guild sync for %s: %s command(s)", guild_id, len(synced))

    synced = await bot.tree.sync()
    logger.info("Global slash sync: %s command(s)", len(synced))
