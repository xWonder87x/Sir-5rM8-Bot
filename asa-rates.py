import requests
import re
import discord
from discord import app_commands

rate_url = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"

# Fetch the current ASA PVE rates
@app_commands.command(name="rates", description="Current ASA Server Rates")
async def rates(interaction: discord.Interaction):
    rate = requests.get(rate_url).text
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
    emb.set_thumbnail(url='https://ark.wiki.gg/images/thumb/0/0a/ASA_Logo_transparent.png/198px-ASA_Logo_transparent.png')
    emb.add_field(name=f"**✨ `{values[2]}x` EXP**", value='', inline=False)
    emb.add_field(name=f"**🌴 `{values[1]}x` Harvesting**", value='', inline=False)
    emb.add_field(name=f"**🦖 `{values[0]}x` Taming**", value='', inline=False)
    emb.add_field(name=f"**💞 `{values[3]}x` Mating Interval**", value='', inline=False)
    emb.add_field(name=f"**🐣 `{values[5]}x` Egg Hatch**", value='', inline=False)
    emb.add_field(name=f"**🐥 `{values[4]}x` Baby Mature**", value='', inline=False)
    emb.add_field(name=f"**🤗 `{values[7]}x` Imprint**", value='', inline=False)
    emb.add_field(name=f"**🤗 `{values[6]}x` Cuddle Interval**", value='', inline=False)
  
    await interaction.response.send_message(embed=emb)