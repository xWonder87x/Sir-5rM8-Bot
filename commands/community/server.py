from __future__ import annotations

import asyncio
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands

import config
import functions
from functions.asa import server_key_from_server
from functions.battlemetrics import fetch_server_uptime_from_asa
from functions.charts import render_server_status_chart


def _fmt_uptime(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


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

        bm = await asyncio.to_thread(fetch_server_uptime_from_asa, data)

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
        embed.add_field(name="Uptime 7d", value=_fmt_uptime(bm.uptime_7), inline=True)
        embed.add_field(name="Uptime 30d", value=_fmt_uptime(bm.uptime_30), inline=True)
        embed.add_field(name="Uptime 90d", value=_fmt_uptime(bm.uptime_90), inline=True)

        if bm.ok and bm.url:
            embed.add_field(
                name="BattleMetrics",
                value=f"[Open server]({bm.url})",
                inline=False,
            )

        status_message = None
        if bm.error == "no_token":
            status_message = "Set BATTLEMETRICS_TOKEN to load uptime history."
            embed.set_footer(text="BattleMetrics token not configured")
        elif bm.error == "not_found":
            status_message = "No BattleMetrics match for this server."
            embed.set_footer(text="BattleMetrics server not found")
        elif bm.error == "fetch_failed":
            status_message = "BattleMetrics uptime request failed."
            embed.set_footer(text="BattleMetrics uptime unavailable")
        elif len(bm.history) < 2:
            status_message = "BattleMetrics returned too little uptime history."
            embed.set_footer(text=f"BattleMetrics uptime · last {config.BM_UPTIME_HISTORY_DAYS}d")
        else:
            embed.set_footer(text=f"BattleMetrics uptime · last {config.BM_UPTIME_HISTORY_DAYS}d")

        chart_bytes = await asyncio.to_thread(
            render_server_status_chart,
            session_name=session_name,
            num_players=num_players,
            max_players=max_players,
            uptime_history=bm.history,
            history_days=config.BM_UPTIME_HISTORY_DAYS,
            uptime_7=bm.uptime_7,
            uptime_30=bm.uptime_30,
            uptime_90=bm.uptime_90,
            status_message=status_message,
        )
        filename = f"serverstatus-{server_key}.png"
        file = discord.File(BytesIO(chart_bytes), filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Server(bot))
