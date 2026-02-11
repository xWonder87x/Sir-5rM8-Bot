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
        result = functions.find_server(server)
        if result is None:
            embed = discord.Embed(
                title="Server Not Found",
                description="I couldn't find that server. It may be offline or the name/number is incorrect.",
                colour=discord.Colour.red()
            )
        else:
            embed = discord.Embed(
                title="Server Online",
                description=result.get("SessionName", "Unknown"),
                colour=discord.Colour.green()
            )
            embed.set_thumbnail(url=config.THUMBNAIL_URL)
            embed.add_field(name="IP Address", value=result.get("IP", "—"), inline=True)
            embed.add_field(name="Players", value=f"{result.get('NumPlayers', 0)}/{result.get('MaxPlayers', 70)}", inline=True)
            embed.add_field(name="Day", value=result.get("DayTime", "—"), inline=True)
            embed.add_field(name="Ping", value=f"{result.get('ServerPing', '—')} ms", inline=True)
            embed.add_field(name="Map", value=result.get("MapName", "—").replace("_WP", ""), inline=True)
            embed.add_field(name="Platform", value=result.get("PlatformType", "—"), inline=True)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Server(bot))
