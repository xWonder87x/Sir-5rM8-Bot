import logging

from discord.ext import commands

logger = logging.getLogger(__name__)

COG_EXTENSIONS: list[tuple[str, str]] = [
    ("commands.core.help", "Help cog loaded"),
    ("commands.core.sync_commands", "Sync commands cog loaded"),
    ("commands.core.admin", "Admin cog loaded"),
    ("commands.community.rates", "Rates cog loaded"),
    ("commands.community.server", "Server status cog loaded"),
    ("commands.community.karma", "Karma cog loaded"),
    ("commands.integrations.ratecheck", "Rate check integration loaded"),
]


async def load_all_extensions(bot: commands.Bot) -> None:
    for ext, msg in COG_EXTENSIONS:
        try:
            await bot.load_extension(ext)
            logger.info(msg)
        except Exception:
            logger.exception("Failed to load extension %s", ext)
            raise
