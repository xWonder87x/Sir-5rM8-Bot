"""Bothunter — catch spam bots via a dedicated trap channel (ported from RiskyMH/honeypot)."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands

from functions import bothunter as bh
from functions import bothunter_cache

logger = logging.getLogger(__name__)


class UnbanView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=24 * 60 * 60)
        self.user_id = user_id

    @discord.ui.button(label="Unban", style=discord.ButtonStyle.secondary)
    async def unban(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not interaction.user:
            return
        member = interaction.user
        if isinstance(member, discord.Member):
            if not member.guild_permissions.ban_members:
                await interaction.response.send_message(
                    "You need the Ban Members permission to unban this user.",
                    ephemeral=True,
                )
                return
        me = interaction.guild.me
        if me is None or not me.guild_permissions.ban_members:
            await interaction.response.send_message(
                "I need the Ban Members permission to unban this user.",
                ephemeral=True,
            )
            return
        try:
            await interaction.guild.unban(
                discord.Object(id=self.user_id),
                reason=f"Unbanned by @{interaction.user} via bothunter log button",
            )
        except discord.NotFound:
            await interaction.response.send_message("This user is not currently banned.", ephemeral=True)
            return
        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't unban that user. Check my role position and Ban Members permission.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"User <@{self.user_id}> has been unbanned by {interaction.user.mention}.",
        )
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except (discord.HTTPException, AttributeError):
            pass


class Bothunter(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._moderating: set[tuple[int, int]] = set()
        self._channel_cache: dict[int, int] | None = None

    def _invalidate_cache(self) -> None:
        self._channel_cache = None

    async def _channel_map(self) -> dict[int, int]:
        if self._channel_cache is None:
            raw = await asyncio.to_thread(bothunter_cache.channel_map)
            self._channel_cache = {int(cid): int(gid) for cid, gid in raw.items()}
        return self._channel_cache

    @app_commands.command(name="bothunter", description="Configure/setup the bothunter trap channel")
    @app_commands.describe(
        channel="Trap channel — anyone who posts here is removed",
        log_channel="Channel for bothunter action logs",
        action="What to do when someone posts in the trap channel",
        no_dm="Don't DM the user when they trigger bothunter",
        no_warning_msg="Don't post/keep a warning message in the trap channel",
        timeout_first="Timeout the user for 1 hour before ban/softban",
        only_recent_delete="Delete only the last 15 minutes of messages (instead of 1 hour)",
        reinvite="Include a rejoin invite link in the DM",
        clear="Clear bothunter config for this server",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Softban (kick + delete messages)", value="softban"),
            app_commands.Choice(name="Ban", value="ban"),
            app_commands.Choice(name="Disabled (log only)", value="disabled"),
        ]
    )
    @app_commands.default_permissions(
        manage_guild=True, ban_members=True, manage_messages=True, manage_channels=True
    )
    @app_commands.guild_only()
    async def bothunter(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
        log_channel: discord.TextChannel | None = None,
        action: app_commands.Choice[str] | None = None,
        no_dm: bool | None = None,
        no_warning_msg: bool | None = None,
        timeout_first: bool | None = None,
        only_recent_delete: bool | None = None,
        reinvite: bool | None = None,
        clear: bool = False,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        guild_id = str(guild.id)

        if clear:
            cfg = await asyncio.to_thread(bothunter_cache.get_config, guild_id)
            if cfg and cfg.get("warning_msg_id") and cfg.get("channel_id"):
                ch = guild.get_channel(int(cfg["channel_id"]))
                if isinstance(ch, discord.TextChannel):
                    try:
                        msg = await ch.fetch_message(int(cfg["warning_msg_id"]))
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            removed = await asyncio.to_thread(bothunter_cache.clear_config, guild_id)
            self._invalidate_cache()
            if removed:
                await interaction.followup.send("Bothunter config cleared for this server.", ephemeral=True)
            else:
                await interaction.followup.send("No bothunter config was set for this server.", ephemeral=True)
            return

        existing = await asyncio.to_thread(bothunter_cache.get_config, guild_id)
        cfg = existing or bh.default_config(guild_id)

        # Status-only when no setup args provided
        setup_args = any(
            x is not None
            for x in (channel, log_channel, action, no_dm, no_warning_msg, timeout_first, only_recent_delete, reinvite)
        )
        if not setup_args:
            if not existing or not existing.get("channel_id"):
                await interaction.followup.send(
                    "Bothunter is not set up yet. Run `/bothunter` with a `channel:` to create the trap.",
                    ephemeral=True,
                )
                return
            count = await asyncio.to_thread(bothunter_cache.get_count, guild_id)
            exps = ", ".join(f"`{e}`" for e in (existing.get("experiments") or [])) or "*(none)*"
            log_disp = (
                f"<#{existing['log_channel_id']}>"
                if existing.get("log_channel_id")
                else "*(not set)*"
            )
            await interaction.followup.send(
                f"**Bothunter status**\n"
                f"- Channel: <#{existing['channel_id']}>\n"
                f"- Log channel: {log_disp}\n"
                f"- Action: **{existing.get('action', 'softban')}**\n"
                f"- Experiments: {exps}\n"
                f"- Moderations: `{count}`",
                ephemeral=True,
            )
            return

        if channel is None and not existing.get("channel_id"):
            await interaction.followup.send(
                "A trap `channel:` is required for first-time setup.",
                ephemeral=True,
            )
            return

        trap = channel or guild.get_channel(int(existing["channel_id"]))
        if not isinstance(trap, discord.TextChannel):
            await interaction.followup.send("Trap channel not found. Pass `channel:` again.", ephemeral=True)
            return

        action_value = bh.normalize_action(action.value if action else cfg.get("action"))
        experiments = set(bh.normalize_experiments(cfg.get("experiments")))

        def _toggle(flag: str, value: bool | None) -> None:
            if value is None:
                return
            if value:
                experiments.add(flag)
            else:
                experiments.discard(flag)

        _toggle("no-dm", no_dm)
        _toggle("no-warning-msg", no_warning_msg)
        _toggle("timeout-first", timeout_first)
        _toggle("only-recent-delete", only_recent_delete)
        _toggle("reinvite", reinvite)

        if "no-dm" in experiments and "reinvite" in experiments:
            await interaction.followup.send(
                "`no_dm` and `reinvite` cannot both be enabled.",
                ephemeral=True,
            )
            return

        me = guild.me
        if me is None:
            await interaction.followup.send("Bot member not available yet. Try again shortly.", ephemeral=True)
            return

        if action_value in ("ban", "softban"):
            if not me.guild_permissions.ban_members:
                await interaction.followup.send(
                    "I need the **Ban Members** permission for softban/ban actions.",
                    ephemeral=True,
                )
                return
            if not trap.permissions_for(me).view_channel or not trap.permissions_for(me).send_messages:
                await interaction.followup.send(
                    f"I need **View Channel** and **Send Messages** in {trap.mention}.",
                    ephemeral=True,
                )
                return

        if "timeout-first" in experiments and not me.guild_permissions.moderate_members:
            await interaction.followup.send(
                "I need the **Timeout Members** permission for `timeout_first`.",
                ephemeral=True,
            )
            return

        log_ch = log_channel
        if log_ch is None and cfg.get("log_channel_id"):
            maybe = guild.get_channel(int(cfg["log_channel_id"]))
            if isinstance(maybe, discord.TextChannel):
                log_ch = maybe

        if log_channel is not None:
            if not log_channel.permissions_for(me).send_messages:
                await interaction.followup.send(
                    f"I need **Send Messages** in {log_channel.mention}.",
                    ephemeral=True,
                )
                return
            try:
                await log_channel.send(
                    f"Bothunter is set up in {trap.mention}. This channel will log bothunter events.",
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    f"I don't have access to post in {log_channel.mention}.",
                    ephemeral=True,
                )
                return

        reinvite_code = cfg.get("reinvite_code")
        if "reinvite" in experiments:
            if not trap.permissions_for(me).create_instant_invite:
                await interaction.followup.send(
                    f"I need **Create Invite** in {trap.mention} for `reinvite`.",
                    ephemeral=True,
                )
                return
            if not reinvite_code or (channel and str(channel.id) != str(cfg.get("channel_id"))):
                try:
                    invite = await trap.create_invite(
                        max_age=0, max_uses=0, unique=False, reason="Bothunter reinvite experiment"
                    )
                    reinvite_code = invite.code
                except discord.HTTPException as exc:
                    await interaction.followup.send(
                        f"Could not create invite for reinvite: {exc}",
                        ephemeral=True,
                    )
                    return
        else:
            reinvite_code = None

        warning_msg_id = cfg.get("warning_msg_id") if str(cfg.get("channel_id")) == str(trap.id) else None
        count = await asyncio.to_thread(bothunter_cache.get_count, guild_id)

        if "no-warning-msg" in experiments:
            if warning_msg_id and str(cfg.get("channel_id")) == str(trap.id):
                try:
                    old = await trap.fetch_message(int(warning_msg_id))
                    await old.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            warning_msg_id = None
        else:
            content = bh.warning_content(count, action_value, cfg.get("warning_message"))
            try:
                if warning_msg_id:
                    try:
                        msg = await trap.fetch_message(int(warning_msg_id))
                        await msg.edit(content=content)
                    except (discord.NotFound, discord.Forbidden):
                        msg = await trap.send(content, allowed_mentions=discord.AllowedMentions.none())
                        warning_msg_id = str(msg.id)
                else:
                    msg = await trap.send(content, allowed_mentions=discord.AllowedMentions.none())
                    warning_msg_id = str(msg.id)
            except discord.Forbidden:
                await interaction.followup.send(
                    f"I couldn't post the warning message in {trap.mention}. "
                    "Check View Channel + Send Messages.",
                    ephemeral=True,
                )
                return

        new_cfg = {
            "guild_id": guild_id,
            "channel_id": str(trap.id),
            "log_channel_id": str(log_ch.id) if log_ch else None,
            "action": action_value,
            "warning_msg_id": warning_msg_id,
            "experiments": sorted(experiments),
            "warning_message": cfg.get("warning_message"),
            "dm_message": cfg.get("dm_message"),
            "log_message": cfg.get("log_message"),
            "reinvite_code": reinvite_code,
        }
        await asyncio.to_thread(bothunter_cache.set_config, new_cfg)
        self._invalidate_cache()

        exps = ", ".join(f"`{e}`" for e in sorted(experiments)) or "*(none)*"
        await interaction.followup.send(
            f"Bothunter config updated!\n"
            f"- Channel: {trap.mention}\n"
            f"- Log channel: {log_ch.mention if log_ch else '*(not set)*'}\n"
            f"- Action: **{action_value}**\n"
            f"- Experiments: {exps}\n\n"
            f"-# Tip: put the trap near the top of your channel list, and keep my role above member roles.",
            ephemeral=True,
        )

    @app_commands.command(name="bothunter-messages", description="Configure bothunter warning/DM/log messages")
    @app_commands.describe(
        warning="Warning shown in the trap channel (empty = default)",
        dm="DM sent to users who trigger bothunter (empty = default)",
        log="Log message posted after moderation (must include {{user:mention}} if custom)",
        reset="Reset all messages to defaults",
    )
    @app_commands.default_permissions(
        manage_guild=True, ban_members=True, manage_messages=True, manage_channels=True
    )
    @app_commands.guild_only()
    async def bothunter_messages(
        self,
        interaction: discord.Interaction,
        warning: str | None = None,
        dm: str | None = None,
        log: str | None = None,
        reset: bool = False,
    ):
        if interaction.guild is None:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild.id)
        cfg = await asyncio.to_thread(bothunter_cache.get_config, guild_id)
        if not cfg or not cfg.get("channel_id"):
            await interaction.followup.send(
                "Set up bothunter first with `/bothunter` before configuring messages.",
                ephemeral=True,
            )
            return

        if reset:
            cfg["warning_message"] = None
            cfg["dm_message"] = None
            cfg["log_message"] = None
        else:
            if warning is not None:
                cfg["warning_message"] = warning.strip() or None
            if dm is not None:
                cfg["dm_message"] = dm.strip() or None
            if log is not None:
                cleaned = log.strip() or None
                if cleaned:
                    required = ("{{user:mention}}", "{{user:ping}}", "{{user:id}}")
                    if not any(v in cleaned for v in required):
                        await interaction.followup.send(
                            "Custom log message must include `{{user:mention}}` (or `{{user:id}}`).",
                            ephemeral=True,
                        )
                        return
                cfg["log_message"] = cleaned

        await asyncio.to_thread(bothunter_cache.set_config, cfg)

        # Refresh warning message in trap channel if present
        if cfg.get("channel_id") and "no-warning-msg" not in (cfg.get("experiments") or []):
            trap = interaction.guild.get_channel(int(cfg["channel_id"]))
            if isinstance(trap, discord.TextChannel):
                count = await asyncio.to_thread(bothunter_cache.get_count, guild_id)
                content = bh.warning_content(
                    count,
                    bh.normalize_action(cfg.get("action")),
                    cfg.get("warning_message"),
                )
                try:
                    if cfg.get("warning_msg_id"):
                        try:
                            msg = await trap.fetch_message(int(cfg["warning_msg_id"]))
                            await msg.edit(content=content)
                        except (discord.NotFound, discord.Forbidden):
                            msg = await trap.send(content, allowed_mentions=discord.AllowedMentions.none())
                            cfg["warning_msg_id"] = str(msg.id)
                            await asyncio.to_thread(bothunter_cache.set_config, cfg)
                    else:
                        msg = await trap.send(content, allowed_mentions=discord.AllowedMentions.none())
                        cfg["warning_msg_id"] = str(msg.id)
                        await asyncio.to_thread(bothunter_cache.set_config, cfg)
                except discord.HTTPException:
                    logger.exception("Failed to refresh bothunter warning message")

        await interaction.followup.send(
            "**Bothunter messages updated.**\n"
            f"- Warning: {'custom' if cfg.get('warning_message') else 'default'}\n"
            f"- DM: {'custom' if cfg.get('dm_message') else 'default'}\n"
            f"- Log: {'custom' if cfg.get('log_message') else 'default'}",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot or message.is_system():
            return
        if message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return

        channel_map = await self._channel_map()
        guild_id = channel_map.get(message.channel.id)
        if guild_id is None or guild_id != message.guild.id:
            return

        await self._handle_trap(message)

    async def _handle_trap(self, message: discord.Message) -> None:
        guild = message.guild
        assert guild is not None
        guild_id = str(guild.id)
        user = message.author
        key = (guild.id, user.id)
        if key in self._moderating:
            return
        self._moderating.add(key)

        try:
            cfg = await asyncio.to_thread(bothunter_cache.get_config, guild_id)
            if not cfg or not cfg.get("channel_id"):
                return
            if str(cfg["channel_id"]) != str(message.channel.id):
                return

            action = bh.normalize_action(cfg.get("action"))
            experiments = set(bh.normalize_experiments(cfg.get("experiments")))

            # Acknowledge quickly
            try:
                await message.add_reaction("🍯")
            except (discord.Forbidden, discord.HTTPException):
                pass

            if action == "disabled":
                return

            member = message.author if isinstance(message.author, discord.Member) else None
            if member is None:
                try:
                    member = await guild.fetch_member(user.id)
                except (discord.NotFound, discord.HTTPException):
                    member = None

            permission_skip: str | False = False
            if member is not None:
                if guild.owner_id == member.id:
                    permission_skip = "owner"
                elif member.guild_permissions.administrator:
                    permission_skip = "admin"

            delete_seconds = 900 if "only-recent-delete" in experiments else 3600
            reinvite_url = None
            if "reinvite" in experiments and cfg.get("reinvite_code"):
                reinvite_url = f"https://discord.gg/{cfg['reinvite_code']}"

            channel_link = f"https://discord.com/channels/{guild.id}/{message.channel.id}/{message.id}"

            # Pre-action: DM + optional timeout (best-effort, ~2s window)
            pre_tasks = []
            if "no-dm" not in experiments:
                pre_tasks.append(
                    self._dm_user(
                        user,
                        action=action,
                        guild_name=guild.name,
                        channel_link=channel_link,
                        reinvite_url=reinvite_url,
                        custom=cfg.get("dm_message"),
                        is_admin=bool(permission_skip),
                        include_reinvite="reinvite" in experiments,
                    )
                )
            if "timeout-first" in experiments and member and not permission_skip:
                pre_tasks.append(self._timeout_member(member, action))

            if pre_tasks:
                await asyncio.wait(
                    [asyncio.create_task(t) for t in pre_tasks],
                    timeout=2.0,
                    return_when=asyncio.ALL_COMPLETED,
                )

            failed: str | bool = False
            if permission_skip:
                failed = "admin"
            else:
                failed = await self._execute_action(guild, user, action, delete_seconds)

            if failed is False and not permission_skip:
                await asyncio.to_thread(
                    bothunter_cache.log_event, guild_id, str(user.id), str(message.channel.id)
                )

            count = await asyncio.to_thread(bothunter_cache.get_count, guild_id)
            await self._send_log(
                guild,
                cfg,
                user=user,
                member=member,
                channel_id=message.channel.id,
                action=action,
                moderated_count=count,
                failed=failed,
                permission_skip=permission_skip,
            )
            await self._refresh_warning(guild, cfg, count)
        except Exception:
            logger.exception("Bothunter trap handler failed in guild %s", guild.id)
        finally:
            self._moderating.discard(key)

    async def _dm_user(
        self,
        user: discord.abc.User,
        *,
        action: bh.BothunterAction,
        guild_name: str,
        channel_link: str,
        reinvite_url: str | None,
        custom: str | None,
        is_admin: bool,
        include_reinvite: bool,
    ) -> None:
        content = bh.dm_content(
            user_id=str(user.id),
            action=action,
            guild_name=guild_name,
            channel_link=channel_link,
            reinvite_url=reinvite_url,
            custom=custom,
            include_reinvite_default=include_reinvite,
        )
        if is_admin:
            content += f"\n-# This is an example message: as an admin you can’t be {bh.ACTION_PAST.get(action, 'removed')}."
        try:
            await user.send(content)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _timeout_member(self, member: discord.Member, action: bh.BothunterAction) -> None:
        try:
            await member.timeout(
                timedelta(hours=1),
                reason=f"Triggered bothunter -> timeout for 1hr before {action}",
            )
        except (discord.Forbidden, discord.HTTPException):
            logger.info("Bothunter timeout-first failed for %s", member.id)

    async def _execute_action(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        action: bh.BothunterAction,
        delete_seconds: int,
    ) -> str | bool:
        try:
            if action == "ban":
                await guild.ban(
                    user,
                    delete_message_seconds=delete_seconds,
                    reason="Triggered bothunter -> ban",
                )
                return False
            if action == "softban":
                await guild.ban(
                    user,
                    delete_message_seconds=delete_seconds,
                    reason="Triggered bothunter -> softban (kick) 1/2",
                )
                await asyncio.sleep(0.25)
                try:
                    await guild.unban(user, reason="Triggered bothunter -> softban (kick) 2/2")
                except discord.NotFound:
                    pass
                except discord.HTTPException:
                    return "unban"
                return False
            return False
        except discord.Forbidden:
            return "permissions"
        except discord.HTTPException:
            logger.exception("Bothunter action failed for user %s", user.id)
            return True

    async def _send_log(
        self,
        guild: discord.Guild,
        cfg: dict,
        *,
        user: discord.abc.User,
        member: discord.Member | None,
        channel_id: int,
        action: bh.BothunterAction,
        moderated_count: int,
        failed: str | bool,
        permission_skip: str | False,
    ) -> None:
        log_id = cfg.get("log_channel_id")
        trap_id = cfg.get("channel_id")
        target_id = int(log_id or trap_id or channel_id)
        channel = guild.get_channel(target_id)
        if not isinstance(channel, discord.TextChannel):
            return

        username = getattr(user, "global_name", None) or user.name
        if permission_skip:
            who = "the **server owner** so I cannot" if permission_skip == "owner" else "a **server admin** so I won't"
            content = (
                f"⚠️ User <@{user.id}> triggered the bothunter, but they are {who} {action} them.\n"
                f"-# Ensure my role is higher than members’ roles and that I have **Ban Members**."
            )
            view = None
        elif failed == "unban" and action == "softban":
            content = (
                f"⚠️ User <@{user.id}> triggered the bothunter, but I failed to **fully** softban them.\n"
                f"-# They may still be banned — unban them manually in Server Settings if needed."
            )
            view = None
        elif failed == "permissions":
            content = (
                f"⚠️ User <@{user.id}> triggered the bothunter, but I **failed** to {action} them.\n"
                f"-# Check that my role is higher than theirs and that I have **Ban Members**."
            )
            view = None
        elif failed:
            content = (
                f"⚠️ User <@{user.id}> triggered the bothunter, but I **failed** to {action} them.\n"
                f"-# This could be a transient Discord issue — please check my permissions."
            )
            view = None
        else:
            content = bh.log_content(
                user_id=str(user.id),
                username=username,
                channel_id=str(channel_id),
                action=action,
                moderated_count=moderated_count,
                custom=cfg.get("log_message"),
            )
            view = UnbanView(user.id) if action == "ban" else None

        try:
            await channel.send(
                content,
                view=view,
                allowed_mentions=discord.AllowedMentions(users=[user]),
            )
        except discord.NotFound:
            if log_id:
                cfg["log_channel_id"] = None
                await asyncio.to_thread(bothunter_cache.set_config, cfg)
        except discord.Forbidden:
            logger.info("Bothunter log send forbidden in guild %s", guild.id)
        except discord.HTTPException:
            logger.exception("Bothunter log send failed in guild %s", guild.id)

    async def _refresh_warning(self, guild: discord.Guild, cfg: dict, count: int) -> None:
        if "no-warning-msg" in (cfg.get("experiments") or []):
            return
        if not cfg.get("channel_id") or not cfg.get("warning_msg_id"):
            return
        channel = guild.get_channel(int(cfg["channel_id"]))
        if not isinstance(channel, discord.TextChannel):
            return
        content = bh.warning_content(
            count,
            bh.normalize_action(cfg.get("action")),
            cfg.get("warning_message"),
        )
        try:
            msg = await channel.fetch_message(int(cfg["warning_msg_id"]))
            await msg.edit(content=content)
        except discord.NotFound:
            cfg["warning_msg_id"] = None
            await asyncio.to_thread(bothunter_cache.set_config, cfg)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        cfg = await asyncio.to_thread(bothunter_cache.get_config, str(channel.guild.id))
        if not cfg:
            return
        changed = False
        if cfg.get("channel_id") == str(channel.id):
            cfg["channel_id"] = None
            cfg["warning_msg_id"] = None
            changed = True
        if cfg.get("log_channel_id") == str(channel.id):
            cfg["log_channel_id"] = None
            changed = True
        if changed:
            await asyncio.to_thread(bothunter_cache.set_config, cfg)
            self._invalidate_cache()


async def setup(bot: commands.Bot):
    await bot.add_cog(Bothunter(bot))
