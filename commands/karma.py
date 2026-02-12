from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils import functions, storage


def _format_by(entry: dict) -> str:
    """Format 'by' field with pingable mention when id available."""
    by_id = entry.get("giver_id") or entry.get("admin_id")
    by_name = entry.get("by", "?")
    if by_id:
        return f"<@{by_id}>"
    return by_name


class Karma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_karma", description="Give 1 karma to a user (24h cooldown per person)")
    @app_commands.describe(
        member="The user to give karma to",
        reason="Reason for giving karma",
    )
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
    async def add_karma(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        giver_id = str(interaction.user.id)
        receiver_id = str(member.id)
        if giver_id == receiver_id:
            await interaction.response.send_message("You can't give karma to yourself!", ephemeral=True)
            return
        settings = functions.get_karma_settings()
        cooldown_hours = settings["cooldown_hours"]
        cooldown = functions.karma_get_cooldown(giver_id, receiver_id)
        if cooldown:
            elapsed = datetime.now(timezone.utc) - cooldown
            remaining = timedelta(hours=cooldown_hours) - elapsed
            if remaining.total_seconds() > 0:
                h = int(remaining.total_seconds() // 3600)
                m = int((remaining.total_seconds() % 3600) // 60)
                await interaction.response.send_message(
                    f"You must wait {h}h {m}m before giving karma to {member.display_name} again.",
                    ephemeral=True
                )
                return
        new_balance = functions.karma_add(
            giver_id,
            receiver_id,
            interaction.user.display_name,
            reason=reason,
        )
        next_available = f" You can give karma to {member.display_name} again in {cooldown_hours}h."
        await interaction.response.send_message(
            f"{member.mention} received 1 karma! Total: **{new_balance}**.{next_available}"
        )

    @app_commands.command(name="remove_karma", description="Remove 1 karma from a user (admin only)")
    @app_commands.describe(member="The user to remove karma from")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_karma(self, interaction: discord.Interaction, member: discord.Member):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        new_balance = functions.karma_take(
            str(member.id),
            str(interaction.user.id),
            interaction.user.display_name,
        )
        if new_balance is None:
            await interaction.response.send_message(f"{member.display_name} has no karma to remove.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"Removed 1 karma from {member.mention}. Total: **{new_balance}**"
            )

    @app_commands.command(name="karma", description="View karma balance")
    @app_commands.describe(member="The user whose karma to check (omit for yourself)")
    async def karma(self, interaction: discord.Interaction, member: discord.Member | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        target = member or interaction.user
        balance = functions.karma_get_balance(str(target.id))
        if target.id == interaction.user.id:
            await interaction.response.send_message(f"You have **{balance}** karma.", ephemeral=True)
        else:
            await interaction.response.send_message(f"{target.display_name} has **{balance}** karma.")

    @app_commands.command(name="karma_history", description="View karma history for a user")
    @app_commands.describe(member="The user whose karma history to view (omit for yourself)")
    async def karma_history(self, interaction: discord.Interaction, member: discord.Member | None = None):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        target = member or interaction.user
        is_admin = interaction.user.guild_permissions.administrator
        if target.id != interaction.user.id and not is_admin:
            await interaction.response.send_message(
                "You can only view your own karma history. Admins can view anyone's.",
                ephemeral=True
            )
            return
        history = functions.karma_get_history(str(target.id))
        if not history:
            await interaction.response.send_message(
                f"No karma history for {target.display_name}.",
                ephemeral=True
            )
            return
        lines = []
        for entry in reversed(history):
            action = "Added" if entry["action"] == "add" else "Removed"
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            by_str = _format_by(entry)
            reason_str = f" — {entry['reason']}" if entry.get("reason") else ""
            lines.append(f"`{ts}`: {action} {entry.get('amount', 1)} by {by_str}{reason_str}")
        msg = f"**Karma history for {target.display_name}:**\n" + "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="karma_audit", description="View recent remove_karma events (admin only)")
    @app_commands.describe(limit="Number of events to show (default 20)")
    @app_commands.checks.has_permissions(administrator=True)
    async def karma_audit(self, interaction: discord.Interaction, limit: int = 20):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        audit = functions.karma_get_audit(limit=min(limit, 50))
        if not audit:
            await interaction.response.send_message("No remove_karma events found.", ephemeral=True)
            return
        lines = []
        for entry in reversed(audit):
            ts = entry.get("timestamp", "")[:19].replace("T", " ")
            target_id = entry.get("user_id", "?")
            admin_str = _format_by(entry)
            lines.append(f"`{ts}`: Removed 1 from <@{target_id}> by {admin_str}")
        msg = "**Recent remove_karma events:**\n" + "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: Exception):
        msg = str(error) if str(error) else type(error).__name__
        if isinstance(error, app_commands.CommandOnCooldown):
            msg = f"Slow down! Try again in {error.retry_after:.0f}s."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"Error: {msg}", ephemeral=True)
            else:
                await interaction.response.send_message(f"Error: {msg}", ephemeral=True)
        except discord.DiscordException:
            pass


async def setup(bot):
    await bot.add_cog(Karma(bot))
