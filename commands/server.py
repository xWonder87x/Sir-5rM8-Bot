from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils import functions, config


class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverstatus", description="Check ASA official server status")
    @app_commands.describe(server="Server name or number (e.g. 5313, TheIsland)")
    async def serverstatus(self, interaction: discord.Interaction, server: str):
        await interaction.response.defer()
        result = await functions.find_server_async(server)
        if result.error == "fetch_failed":
            embed = discord.Embed(
                title="Could Not Reach ASA Servers",
                description="The official server list is unavailable right now. Please try again in a few minutes.",
                colour=discord.Colour.orange(),
            )
        elif not result.ok:
            embed = discord.Embed(
                title="Server Not Found",
                description="I couldn't find that server. It may be offline or the name/number is incorrect.",
                colour=discord.Colour.red(),
            )
        else:
            data = result.server
            embed = discord.Embed(
                title="Server Online",
                description=data.get("SessionName", "Unknown"),
                colour=discord.Colour.green(),
            )
            embed.set_thumbnail(url=config.THUMBNAIL_URL)
            embed.add_field(name="IP Address", value=data.get("IP", "—"), inline=True)
            embed.add_field(
                name="Players",
                value=f"{data.get('NumPlayers', 0)}/{data.get('MaxPlayers', 70)}",
                inline=True,
            )
            embed.add_field(name="Day", value=data.get("DayTime", "—"), inline=True)
            embed.add_field(name="Ping", value=f"{data.get('ServerPing', '—')} ms", inline=True)
            embed.add_field(name="Map", value=data.get("MapName", "—").replace("_WP", ""), inline=True)
            embed.add_field(name="Platform", value=data.get("PlatformType", "—"), inline=True)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Server(bot))
