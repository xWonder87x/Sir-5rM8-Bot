import discord
from discord.ext import tasks, commands
from utils import config, constants, functions


class RateCheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _build_embed(self, current: dict, previous: dict | None = None) -> discord.Embed:
        """Build rates embed, optionally marking changed values."""
        emb = discord.Embed(
            title='ASA Official Server Rates',
            description="",
            colour=discord.Colour.pink()
        )
        emb.set_thumbnail(url=config.THUMBNAIL_URL)

        for emoji, label, key in constants.RATE_DISPLAY:
            value = current.get(key, "?")
            if previous and previous.get(key) != value:
                name = f"**{emoji} `{value}x` {label}** *(changed)*"
            else:
                name = f"**{emoji} `{value}x` {label}**"
            emb.add_field(name=name, value='', inline=False)
        return emb

    @tasks.loop(minutes=1)
    async def ratecheck(self):
        serverlist, current, previous, flag = functions.check_rate_changes()
        if flag == 0:
            embed = self._build_embed(current, previous)
            for ent in serverlist:
                try:
                    guild = self.bot.get_guild(int(ent['server_id']))
                    channel = guild.get_channel(int(ent['channel_id'])) if guild else None
                    role = guild.get_role(int(ent['role'])) if guild else None
                    if not channel or not role:
                        continue
                    await channel.send(
                        f"{role.mention} — ASA rates have changed!",
                        embed=embed
                    )
                except (KeyError, AttributeError, discord.Forbidden) as e:
                    print(f"Rate notification skipped for guild {ent.get('server_id', '?')}: {e}")


async def setup(bot):
    await bot.add_cog(RateCheckCog(bot))
