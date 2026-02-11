import discord
from discord import app_commands
from discord.ext import commands
from utils import config, functions

# Display order: (emoji, label, rate_key)
RATE_DISPLAY = [
    ("✨", "EXP", "XPMultiplier"),
    ("🌴", "Harvesting", "HarvestAmountMultiplier"),
    ("🦖", "Taming", "TamingSpeedMultiplier"),
    ("💞", "Mating Interval", "MatingIntervalMultiplier"),
    ("🐣", "Egg Hatch", "EggHatchSpeedMultiplier"),
    ("🐤", "Baby Mature", "BabyMatureSpeedMultiplier"),
    ("🤗", "Imprint", "BabyImprintAmountMultiplier"),
    ("🤗", "Cuddle Interval", "BabyCuddleIntervalMultiplier"),
]


class Rates(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="rates", description="Current ASA Server Rates")
    async def rates(self, interaction: discord.Interaction):
        rate_data = functions.fetch_current_rates()
        if not rate_data:
            await interaction.response.send_message(
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
        for emoji, label, key in RATE_DISPLAY:
            value = rate_data.get(key, "?")
            emb.add_field(name=f"**{emoji} `{value}x` {label}**", value='', inline=False)

        await interaction.response.send_message(embed=emb)


async def setup(bot):
    await bot.add_cog(Rates(bot))
