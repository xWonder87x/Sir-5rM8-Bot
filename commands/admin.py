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
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        functions.add_server_channel(str(interaction.guild.id), str(channel.id), str(role.id))
        await interaction.response.send_message(f"{channel.mention} is set for automatic Official PVE rates updates.")
        try:
            await channel.send("This channel is set for automatic Official PVE rates updates.")
        except discord.Forbidden:
            await interaction.followup.send("Configured, but I couldn't post in that channel.", ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: Exception):
        msg = str(error) if str(error) else type(error).__name__
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"Error: {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error: {msg}", ephemeral=True)
        except discord.DiscordException:
            pass


async def setup(bot):
    await bot.add_cog(Admin(bot))