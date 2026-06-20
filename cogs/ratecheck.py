from __future__ import annotations

import logging

import discord
from discord.ext import tasks, commands

from utils import config, constants, functions

logger = logging.getLogger(__name__)


class RateCheckCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        self.ratecheck.cancel()

    def _build_embed(self, current: dict) -> discord.Embed:
        emb = discord.Embed(
            title='ASA Official Server Rates',
            description="",
            colour=discord.Colour.pink()
        )
        emb.set_thumbnail(url=config.THUMBNAIL_URL)

        for emoji, label, key in constants.RATE_DISPLAY:
            value = current.get(key, "?")
            emb.add_field(name=f"**{emoji} `{value}x` {label}**", value='', inline=False)
        return emb

    @tasks.loop(minutes=1)
    async def ratecheck(self):
        serverlist, current, _, flag = await functions.check_rate_changes_async()
        if flag == 0:
            embed = self._build_embed(current)
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
                    logger.warning(
                        "Rate notification skipped for guild %s: %s",
                        ent.get('server_id', '?'),
                        e,
                    )


async def setup(bot):
    await bot.add_cog(RateCheckCog(bot))
