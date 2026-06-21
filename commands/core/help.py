from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config


def _embed(title: str, description: str) -> discord.Embed:
    emb = discord.Embed(title=title, description=description, colour=discord.Colour.pink())
    emb.set_thumbnail(url=config.THUMBNAIL_URL)
    return emb


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Setup guide and command reference")
    async def help(self, interaction: discord.Interaction):
        embeds = [
            _embed(
                "Sir-5rM8 · Help",
                "Quick setup guide for server owners. Making the community better, one command at a time.",
            ),
            _embed(
                "ASA Official PVE Rate Fetch & Dynamic Rate Monitoring",
                "`/rates`\n"
                "`/set_rate_channel [channel] [role]`\n"
                "`/rate_channel_status`\n"
                "`/clear_rate_channel`",
            ),
            _embed(
                "Server Status",
                "`/serverstatus [server]`",
            ),
            _embed(
                "Karma System",
                "`/karma [member] [reason]`\n"
                "`/manage_karma action:check [member]`\n"
                "`/manage_karma action:history [member]`\n"
                "`/manage_karma action:remove [member]` *(Admin)*\n"
                "`/manage_karma action:audit` *(Admin)*",
            ),
            _embed(
                "Admin Tools",
                "`/say [message]`\n"
                "`/sync-commands` *(Admin)* — refresh slash commands\n"
                "`/servers` *(Admin)* — list every server the bot is in\n\n"
                "**Quick Start**\n"
                "1. Try `/rates` and `/serverstatus server:5313`\n"
                "2. Optional: `/set_rate_channel` for rate alerts\n"
                "3. Use `/karma` to reward helpful members",
            ),
        ]

        await interaction.response.send_message(embeds=embeds)


async def setup(bot):
    await bot.add_cog(Help(bot))
