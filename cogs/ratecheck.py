import re
import discord
from discord.ext import tasks, commands
from utils import functions, config

class RateCheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(minutes=1)
    async def ratecheck(self):
        serverlist, data, flag = functions.loop()
        if flag == 0:
            pattern = r"^\s*([\w.]+)\s*=\s*([\w.-]+)\s*$"
            values = []
            for line in data.split('\n'):
                match = re.match(pattern, line)
                if match:
                    values.append(match.groups()[1])

            for ent in serverlist:
                try:
                    guild = self.bot.get_guild(int(ent['server_id']))
                    channel = guild.get_channel(int(ent['channel_id']))
                    role = guild.get_role(int(ent['role']))
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
                    await channel.send(embed=emb)
                    await channel.send(f"The {role.mention} have changed!")
                except KeyError:
                    print("Server channel missing or something else went wrong!")

async def setup(bot):
    await bot.add_cog(RateCheckCog(bot))