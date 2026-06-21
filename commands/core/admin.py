from __future__ import annotations

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

import config
import db
import functions
from db.migrate_json import (
    DatabaseHasDataError,
    MigrationError,
    NoJsonDataError,
    SupabaseNotConfiguredError,
    preview_migration,
    run_migration,
)

try:
    from httpx import ConnectError as HttpxConnectError
except ImportError:
    HttpxConnectError = ()

def _paginate_lines(header: str, lines: list[str]) -> list[str]:
    """Split lines into Discord messages under the character limit."""
    max_len = config.DISCORD_MESSAGE_MAX
    if not lines:
        return [header]

    pages: list[str] = []
    idx = 0
    part = 1
    while idx < len(lines):
        page_header = header if part == 1 else f"{header} (continued {part})"
        chunk: list[str] = []
        while idx < len(lines):
            body = "\n".join(chunk + [lines[idx]])
            if len(f"{page_header}\n{body}") <= max_len:
                chunk.append(lines[idx])
                idx += 1
            elif chunk:
                break
            else:
                chunk.append(lines[idx][: max(0, max_len - len(page_header) - 2)] + "…")
                idx += 1
                break
        pages.append(f"{page_header}\n" + "\n".join(chunk))
        part += 1
    return pages


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Repeats a message (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("Done.", ephemeral=True)
        if interaction.channel:
            await interaction.channel.send(message)

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

    @app_commands.command(
        name="migrate-json-to-db",
        description="Import JSON file data into Supabase (admin only)",
    )
    @app_commands.describe(
        apply="Write to Supabase (default: preview counts only)",
        force="Overwrite existing DB rows and append karma events again",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def migrate_json_to_db(
        self,
        interaction: discord.Interaction,
        apply: bool = False,
        force: bool = False,
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            if apply:
                if not db.use_supabase():
                    raise SupabaseNotConfiguredError(
                        "Supabase is not configured. Set SUPABASE_URL and credentials in .env."
                    )
                result = await asyncio.to_thread(run_migration, force=force)
                counts = result.database_counts
                body = (
                    f"{result.source.format('Imported from JSON')}\n\n"
                    f"**Database row counts**\n"
                    f"guild_rate_notifications: {counts['guild_rate_notifications']}\n"
                    f"karma_balances: {counts['karma_balances']}\n"
                    f"karma_cooldowns: {counts['karma_cooldowns']}\n"
                    f"karma_events: {counts['karma_events']}\n"
                    f"rate_state_has_data: {counts['rate_state_has_data']}"
                )
                await interaction.followup.send(
                    f"Migration applied successfully.\n\n{body}",
                    ephemeral=True,
                )
            else:
                summary = await asyncio.to_thread(preview_migration)
                await interaction.followup.send(
                    f"Preview only — no changes written. Re-run with `apply: True` to import.\n\n"
                    f"{summary.format('JSON source')}",
                    ephemeral=True,
                )
        except DatabaseHasDataError as exc:
            await interaction.followup.send(
                f"{exc}\n\nRe-run with `force: True` if you want to proceed anyway.",
                ephemeral=True,
            )
        except (SupabaseNotConfiguredError, NoJsonDataError, MigrationError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)

    @app_commands.command(name="servers", description="List every server the bot is in (admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def servers(self, interaction: discord.Interaction):
        guilds = self.bot.guilds
        count = len(guilds)
        lines = [f"**{g.name}** — `{g.id}`" for g in sorted(guilds, key=lambda g: g.name.lower())]
        header = f"**Servers ({count}):**"
        pages = _paginate_lines(header, lines) if lines else [f"**Servers (0):**\nNo servers."]
        await interaction.response.send_message(pages[0], ephemeral=True)
        for page in pages[1:]:
            await interaction.followup.send(page, ephemeral=True)

    async def cog_app_command_error(self, interaction: discord.Interaction, error: Exception):
        if isinstance(error, HttpxConnectError) or "Name or service not known" in str(error):
            msg = (
                "Could not reach Supabase (DNS/network). "
                "Check **SUPABASE_URL** in `.env` — use `https://YOUR_PROJECT.supabase.co` "
                "(Project Settings → API). "
                "If the host has no outbound internet, remove `SUPABASE_URL` and "
                "`SUPABASE_SERVICE_KEY` to use local JSON storage instead."
            )
        else:
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