from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

import functions
from commands.community.rate_roles import RateRoleView, build_rates_embed


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

        view = RateRoleView() if interaction.guild else None
        await interaction.followup.send(embed=build_rates_embed(rate_data), view=view)


async def setup(bot):
    bot.add_view(RateRoleView())
    await bot.add_cog(Rates(bot))
