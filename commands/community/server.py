from __future__ import annotations

import asyncio
import logging
import os
import re
from collections import defaultdict
from io import BytesIO

import discord
from discord import app_commands
from discord.ext import commands, tasks

import config
import db
from functions.asa import fetch_official_servers, match_server_key_in_list
from functions.charts import render_server_status_chart
from functions.server_status import ResolvedServer, resolve_from_asa_server, resolve_server_status

logger = logging.getLogger(__name__)

_MENTION_BATCH = 40


def _fmt_uptime(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


def _status_embed_and_chart(resolved: ResolvedServer) -> tuple[discord.Embed, bytes, str]:
    bm = resolved.bm
    title = "Server Online" if resolved.online else "Server Offline"
    colour = discord.Colour.green() if resolved.online else discord.Colour.red()
    embed = discord.Embed(
        title=title,
        description=resolved.session_name,
        colour=colour,
    )
    embed.set_thumbnail(url=config.THUMBNAIL_URL)
    embed.add_field(name="IP Address", value=resolved.ip or "—", inline=True)
    embed.add_field(
        name="Players",
        value=f"{resolved.num_players}/{resolved.max_players}",
        inline=True,
    )
    embed.add_field(name="Day", value=resolved.day, inline=True)
    embed.add_field(name="Ping", value=resolved.ping, inline=True)
    embed.add_field(name="Map", value=resolved.map_name, inline=True)
    embed.add_field(name="Platform", value=resolved.platform, inline=True)
    embed.add_field(name="Uptime 7d", value=_fmt_uptime(bm.uptime_7 if bm else None), inline=True)
    embed.add_field(name="Uptime 30d", value=_fmt_uptime(bm.uptime_30 if bm else None), inline=True)
    embed.add_field(name="Uptime 90d", value=_fmt_uptime(bm.uptime_90 if bm else None), inline=True)

    if bm and bm.ok and bm.url:
        embed.add_field(
            name="BattleMetrics",
            value=f"[Open server]({bm.url})",
            inline=False,
        )

    status_message = None
    if bm is None or bm.error == "no_token":
        status_message = "Set BATTLEMETRICS_TOKEN to load uptime history."
        embed.set_footer(text="BattleMetrics token not configured")
    elif bm.error == "not_found":
        status_message = "No BattleMetrics match for this server."
        embed.set_footer(text="BattleMetrics server not found")
    elif bm.error == "fetch_failed":
        status_message = "BattleMetrics uptime request failed."
        embed.set_footer(text="BattleMetrics uptime unavailable")
    elif len(bm.history) < 2:
        status_message = "BattleMetrics returned too little uptime history."
        embed.set_footer(text=f"BattleMetrics uptime · last {config.BM_UPTIME_HISTORY_DAYS}d")
    else:
        embed.set_footer(text=f"BattleMetrics uptime · last {config.BM_UPTIME_HISTORY_DAYS}d")

    chart_bytes = render_server_status_chart(
        session_name=resolved.session_name,
        num_players=resolved.num_players,
        max_players=resolved.max_players,
        uptime_history=bm.history if bm else [],
        history_days=config.BM_UPTIME_HISTORY_DAYS,
        uptime_7=bm.uptime_7 if bm else None,
        uptime_30=bm.uptime_30 if bm else None,
        uptime_90=bm.uptime_90 if bm else None,
        status_message=status_message,
    )
    filename = f"serverstatus-{resolved.server_key or 'unknown'}.png"
    return embed, chart_bytes, filename


class NotifyWhenUpButton(discord.ui.DynamicItem[discord.ui.Button], template=r"s5up:(?P<key>[A-Za-z0-9._-]{1,80})"):
    def __init__(self, server_key: str) -> None:
        self.server_key = server_key
        super().__init__(
            discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="Notify me when it's up",
                custom_id=f"s5up:{server_key}",
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item,
        match: re.Match[str],
        /,
    ):
        return cls(match["key"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel_id
        if channel_id is None:
            await interaction.followup.send(
                "I can only subscribe you from a channel.",
                ephemeral=True,
            )
            return

        servers = await asyncio.to_thread(fetch_official_servers)
        if servers is not None:
            found = match_server_key_in_list(servers, self.server_key)
            if found:
                await interaction.followup.send(
                    "That server is already online — try `/serverstatus` again.",
                    ephemeral=True,
                )
                return
        elif servers is None:
            await interaction.followup.send(
                "I couldn't reach the official server list just now. Try the button again in a minute.",
                ephemeral=True,
            )
            return

        added = await asyncio.to_thread(
            db.add_up_notify,
            self.server_key,
            str(interaction.user.id),
            str(channel_id),
            str(interaction.guild_id) if interaction.guild_id else None,
            self.server_key,
            None,
        )
        if added:
            await interaction.followup.send(
                "I'll ping you here when that server comes back online.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                "You're already on the list for this server.",
                ephemeral=True,
            )


class Server(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self) -> None:
        if os.environ.get("EXTENSION_VERIFY"):
            return
        if not self.check_up_notifies.is_running():
            self.check_up_notifies.start()

    def cog_unload(self) -> None:
        self.check_up_notifies.cancel()
        self.bot.remove_dynamic_items(NotifyWhenUpButton)

    @app_commands.command(name="serverstatus", description="Check ASA official server status")
    @app_commands.describe(server="Server name or number (e.g. 5313, TheIsland)")
    async def serverstatus(self, interaction: discord.Interaction, server: str):
        await interaction.response.defer()
        resolved = await asyncio.to_thread(resolve_server_status, server)
        if resolved.error == "fetch_failed":
            embed = discord.Embed(
                title="Could Not Reach ASA Servers",
                description="The official server list is unavailable right now. Please try again in a few minutes.",
                colour=discord.Colour.orange(),
            )
            await interaction.followup.send(embed=embed)
            return
        if not resolved.ok:
            embed = discord.Embed(
                title="Server Not Found",
                description="I couldn't find that server. It may be offline or the name/number is incorrect.",
                colour=discord.Colour.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        embed, chart_bytes, filename = await asyncio.to_thread(_status_embed_and_chart, resolved)
        file = discord.File(BytesIO(chart_bytes), filename=filename)
        embed.set_image(url=f"attachment://{filename}")
        view = None
        if not resolved.online and resolved.server_key:
            view = discord.ui.View(timeout=None)
            view.add_item(NotifyWhenUpButton(resolved.server_key))
        await interaction.followup.send(embed=embed, file=file, view=view)

    @tasks.loop(minutes=config.SERVER_UP_CHECK_MINUTES)
    async def check_up_notifies(self):
        keys = await asyncio.to_thread(db.list_up_notify_keys)
        if not keys:
            return
        servers = await asyncio.to_thread(fetch_official_servers)
        if servers is None:
            logger.warning("Up-notify check skipped: official ASA list unavailable")
            return
        for key in keys:
            found = match_server_key_in_list(servers, key)
            if not found:
                continue
            watchers = await asyncio.to_thread(db.list_up_notify_watchers, key)
            if not watchers:
                continue
            query = next((str(w.get("query") or "") for w in watchers if w.get("query")), key)
            try:
                resolved = await asyncio.to_thread(resolve_from_asa_server, found, query)
                embed, chart_bytes, filename = await asyncio.to_thread(_status_embed_and_chart, resolved)
            except Exception:
                logger.exception("Failed to build up-notify status for %s", key)
                continue
            by_channel: dict[str, list[str]] = defaultdict(list)
            for watcher in watchers:
                cid = str(watcher.get("channel_id") or "")
                uid = str(watcher.get("user_id") or "")
                if cid and uid and uid not in by_channel[cid]:
                    by_channel[cid].append(uid)
            for channel_id, user_ids in by_channel.items():
                ok = await self._send_up_notify(channel_id, user_ids, embed, chart_bytes, filename)
                if ok:
                    await asyncio.to_thread(db.clear_up_notify, key, channel_id)

    @check_up_notifies.before_loop
    async def before_check_up_notifies(self):
        await self.bot.wait_until_ready()

    async def _send_up_notify(
        self,
        channel_id: str,
        user_ids: list[str],
        embed: discord.Embed,
        chart_bytes: bytes,
        filename: str,
    ) -> bool:
        try:
            cid = int(channel_id)
        except (TypeError, ValueError):
            return True
        channel = self.bot.get_channel(cid)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(cid)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                logger.warning("Up-notify channel %s unavailable: %s", channel_id, exc)
                return True
        if not hasattr(channel, "send"):
            logger.warning("Up-notify channel %s is not messageable", channel_id)
            return True
        mentions = [f"<@{uid}>" for uid in user_ids]
        allowed = discord.AllowedMentions(users=True, roles=False, everyone=False)
        try:
            first = True
            for i in range(0, len(mentions), _MENTION_BATCH):
                batch = " ".join(mentions[i : i + _MENTION_BATCH])
                content = f"{batch} — that server is back online."
                if first:
                    file = discord.File(BytesIO(chart_bytes), filename=filename)
                    chart_embed = embed.copy()
                    chart_embed.set_image(url=f"attachment://{filename}")
                    await channel.send(
                        content=content,
                        embed=chart_embed,
                        file=file,
                        allowed_mentions=allowed,
                    )
                    first = False
                else:
                    await channel.send(content=content, allowed_mentions=allowed)
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Up-notify send failed in channel %s: %s", channel_id, exc)
            return False


async def setup(bot):
    bot.add_dynamic_items(NotifyWhenUpButton)
    await bot.add_cog(Server(bot))
