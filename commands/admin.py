import discord
from discord import app_commands
from discord.ext import commands
from utils import functions

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="set_rate_channel", description="Set channel for rate updates")
    @app_commands.describe(channel="Channel", role="Role")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_rate_channel(self, interaction: discord.Interaction, channel: discord.TextChannel, role: discord.Role):
        functions.add_server_channel(str(interaction.guild.id), str(channel.id), str(role.id))
        await channel.send("This channel is set for automatic Official PVE rates updates.")
        await interaction.response.send_message(f"{channel.mention} is set for automatic Official PVE rates updates.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(error, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Admin(bot))