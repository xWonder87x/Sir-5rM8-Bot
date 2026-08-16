from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

import config
import db
import functions
from functions.asa import server_key_from_server
from functions.charts import render_server_status_chart


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
            await interaction.followup.send(embed=embed)
            return
        if not result.ok:
            embed = discord.Embed(
                title="Server Not Found",
                description="I couldn't find that server. It may be offline or the name/number is incorrect.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        data = result.server
        session_name = data.get("SessionName", "Unknown")
        num_players = int(data.get("NumPlayers") or 0)
        max_players = int(data.get("MaxPlayers") or 70)
        server_key = server_key_from_server(data)

        def _persist_and_history() -> list[dict]:
            db.watch_server(server_key, session_name)
            db.record_server_sample(server_key, num_players, max_players)
            return db.get_server_player_history(
                server_key, hours=config.SERVER_HISTORY_HOURS
            )

        history = await asyncio.to_thread(_persist_and_history)

        embed = discord.Embed(
            title="Server Online",
            description=session_name,
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url=config.THUMBNAIL_URL)
        embed.add_field(name="IP Address", value=data.get("IP", "—"), inline=True)
        embed.add_field(
            name="Players",
            value=f"{num_players}/{max_players}",
            inline=True,
        )
        embed.add_field(name="Day", value=data.get("DayTime", "—"), inline=True)
        embed.add_field(name="Ping", value=f"{data.get('ServerPing', '—')} ms", inline=True)
        embed.add_field(name="Map", value=data.get("MapName", "—").replace("_WP", ""), inline=True)
        embed.add_field(name="Platform", value=data.get("PlatformType", "—"), inline=True)
        if len(history) < 2:
            embed.set_footer(
                text=f"Player history builds every {config.SERVER_SAMPLE_INTERVAL_MINUTES}m after first lookup"
            )
        else:
            embed.set_footer(text=f"Player history · last {config.SERVER_HISTORY_HOURS}h")

        chart_bytes = await asyncio.to_thread(
            render_server_status_chart,
            session_name=session_name,
            num_players=num_players,
            max_players=max_players,
            history=history,
            history_hours=config.SERVER_HISTORY_HOURS,
        )
        filename = f"serverstatus-{server_key}.png"
        file = discord.File(BytesIO(chart_bytes), filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Server(bot))
