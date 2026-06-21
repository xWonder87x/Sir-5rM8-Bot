from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import config
import functions


class Rates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rates", description="Current ASA Server Rates")
    async def rates(self, interaction: discord.Interaction):
        await interaction.response.defer()
        rate_data = await functions.fetch_current_rates_async()
        if not rate_data:
            await interaction.followup.send(
                "Could not fetch rates. Please try again later.",
                ephemeral=True
            )
            return

        emb = discord.Embed(
            title='ASA Official Server Rates',
            description="",
            colour=discord.Colour.pink()
        )
        emb.set_thumbnail(url=config.THUMBNAIL_URL)
        for emoji, label, key in config.RATE_DISPLAY:
            value = rate_data.get(key, "?")
            emb.add_field(name=f"**{emoji} `{value}x` {label}**", value='', inline=False)

        await interaction.followup.send(embed=emb)


async def setup(bot):
    await bot.add_cog(Rates(bot))
