import discord
from discord import app_commands
from discord.ext import commands
from utils import functions

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Repeats a message (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)

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

    @app_commands.command(name="rate_channel_status", description="Show current rate notification setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def rate_channel_status(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        rn = functions.get_server_channel(str(interaction.guild.id))
        if not rn:
            await interaction.response.send_message(
                "No rate channel configured. Use `/set_rate_channel` to set one.",
                ephemeral=True
            )
            return
        channel = interaction.guild.get_channel(int(rn["channel_id"]))
        role = interaction.guild.get_role(int(rn["role_id"]))
        channel_str = channel.mention if channel else f"#{rn['channel_id']} (deleted?)"
        role_str = role.mention if role else f"@{rn['role_id']} (deleted?)"
        await interaction.response.send_message(
            f"**Rate notifications:** {channel_str} → {role_str}",
            ephemeral=True
        )

    @app_commands.command(name="clear_rate_channel", description="Remove rate notification setup")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear_rate_channel(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        if functions.clear_server_channel(str(interaction.guild.id)):
            await interaction.response.send_message("Rate notifications disabled for this server.", ephemeral=True)
        else:
            await interaction.response.send_message("No rate channel was configured.", ephemeral=True)

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