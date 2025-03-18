import requests
import re
import discord
from discord import app_commands
from discord.ext import commands
from utils import config

class Rates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rates", description="Current ASA Server Rates")
    async def rates(self, interaction: discord.Interaction):
        rate = requests.get(config.RATE_URL).text
        pattern = r"^\s*([\w.]+)\s*=\s*([\w.-]+)\s*$"
        values = []
        for line in rate.split('\n'):
            match = re.match(pattern, line)
            if match:
                values.append(match.groups()[1])

        emb = discord.Embed(
            title='ASA Official Server Rates',
            description="",
            colour=discord.Colour.pink()
        )
        emb.set_thumbnail(url=config.THUMBNAIL_URL)
        emb.add_field(name=f"**✨ `{values[4]}x` EXP**", value='', inline=False)
        emb.add_field(name=f"**🌴 `{values[3]}x` Harvesting**", value='', inline=False)
        emb.add_field(name=f"**🦖 `{values[2]}x` Taming**", value='', inline=False)
        emb.add_field(name=f"**💞 `{values[5]}x` Mating Interval**", value='', inline=False)
        emb.add_field(name=f"**🐣 `{values[7]}x` Egg Hatch**", value='', inline=False)
        emb.add_field(name=f"**🐤 `{values[6]}x` Baby Mature**", value='', inline=False)
        emb.add_field(name=f"**🤗 `{values[9]}x` Imprint**", value='', inline=False)
        emb.add_field(name=f"**🤗 `{values[8]}x` Cuddle Interval**", value='', inline=False)
    
        await interaction.response.send_message(embed=emb)

async def setup(bot):
    await bot.add_cog(Rates(bot))