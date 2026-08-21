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
                "`/rates` — **Subscribe** / **Unsubscribe** for the alert role\n"
                "`/set_rate_channel [channel] [role]`\n"
                "`/rate_channel_status`\n"
                "`/clear_rate_channel`",
            ),
            _embed(
                "Server Status",
                "`/serverstatus [server]`\n"
                "If a server is offline, tap **Notify me when it's up** or **Report Outage**.",
            ),
            _embed(
                "Official in-game ARK notifications",
                "`/arknotifications` *(Admin)* — pick a channel for the same notices "
                "Wildcard posts inside ASA. Restart countdowns replace the previous "
                "timer; `execsave` is not posted. Use **Disable** to stop.",
            ),
            _embed(
                "Bothunter (spam trap)",
                "`/bothunter [channel] [log_channel] [action] …` *(Admin)*\n"
                "`/bothunter-messages [warning] [dm] [log]` *(Admin)*\n\n"
                "Anyone posting in the trap channel is softbanned/banned automatically.",
            ),
            _embed(
                "Admin Tools",
                "`/say [message]`\n"
                "`/sync-commands` *(Admin)* — refresh slash commands\n\n"
                "**Quick Start**\n"
                "1. Try `/rates` and `/serverstatus server:5313`\n"
                "2. Optional: `/set_rate_channel` for rate alerts\n"
                "3. Optional: `/arknotifications` for in-game Wildcard notices\n"
                "4. Optional: `/bothunter` to catch spam bots",
            ),
        ]

        await interaction.response.send_message(embeds=embeds)


async def setup(bot):
    await bot.add_cog(Help(bot))
