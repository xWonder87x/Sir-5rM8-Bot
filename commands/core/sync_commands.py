import logging

import discord
from discord import app_commands
from discord.ext import commands

from commands.core.command_sync import sync_application_commands

logger = logging.getLogger(__name__)


class SyncCommandsCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="sync-commands", description="Admin: force slash command sync.")
    @app_commands.default_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            await sync_application_commands(self.bot)
        except Exception:
            logger.exception("Manual slash sync failed")
            await interaction.followup.send("Sync failed — check bot logs.", ephemeral=True)
            return
        await interaction.followup.send("Slash commands synced.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SyncCommandsCog(bot))
