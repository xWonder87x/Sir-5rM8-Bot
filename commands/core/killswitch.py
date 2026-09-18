"""Owner-only kill switch: when on, block all slash commands except /killswitch."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Coroutine

import discord
from discord import app_commands
from discord.ext import commands

import config
import db

logger = logging.getLogger(__name__)

TreeCheck = Callable[[discord.Interaction], Coroutine[Any, Any, bool]]
TreeError = Callable[
    [discord.Interaction, app_commands.AppCommandError], Coroutine[Any, Any, None]
]


class KillswitchActive(app_commands.CheckFailure):
    """Raised when kill switch blocks a slash command."""


def killswitch_owner_user_id() -> int | None:
    override = os.environ.get("KILLSWITCH_USER_ID", "").strip()
    if override.isdigit():
        return int(override)
    configured = getattr(config, "KILLSWITCH_USER_ID", None)
    if configured is not None:
        try:
            return int(configured)
        except (TypeError, ValueError):
            pass
    owner = getattr(config, "RESTART_NOTIFY_USER_ID", None)
    if owner is None:
        return None
    try:
        return int(owner)
    except (TypeError, ValueError):
        return None


def db_state_persist_available() -> bool:
    if not hasattr(db, "get_state") or not hasattr(db, "set_state"):
        return False
    if hasattr(db, "use_remote_db"):
        return bool(db.use_remote_db())
    if hasattr(db, "use_postgres"):
        return bool(db.use_postgres())
    return False


def interaction_command_name(interaction: discord.Interaction) -> str | None:
    data = interaction.data
    if not isinstance(data, dict):
        return None
    name = data.get("name")
    return name if isinstance(name, str) else None


class KillswitchCog(commands.Cog):
    """`/killswitch on|off` — bot owner only."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._enabled = False
        self._previous_check: TreeCheck | None = None
        self._previous_error: TreeError | None = None
        self._installed = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def cog_load(self) -> None:
        await self._load_state()
        self._install_tree_hooks()
        logger.info(
            "Kill switch ready: enabled=%s owner=%s",
            self._enabled,
            killswitch_owner_user_id(),
        )

    async def cog_unload(self) -> None:
        self._restore_tree_hooks()

    async def _load_state(self) -> None:
        if not db_state_persist_available():
            self._enabled = False
            return
        try:
            state = await db.get_state(db.killswitch_key())
        except Exception:
            # Fail closed: if we cannot read persisted state, keep slash commands
            # blocked until a successful load rather than silently re-enabling.
            logger.exception(
                "Failed to load kill switch state; defaulting to on (fail-closed)"
            )
            self._enabled = True
            return
        self._enabled = bool(state.get("enabled", False))

    async def _persist(self, enabled: bool) -> bool:
        if db_state_persist_available():
            try:
                await db.set_state(db.killswitch_key(), {"enabled": enabled})
            except Exception:
                logger.exception("Failed to persist kill switch state=%s", enabled)
                return False
        self._enabled = enabled
        return True

    def _install_tree_hooks(self) -> None:
        if self._installed:
            return
        tree = self.bot.tree
        previous_check = tree.interaction_check
        previous_error = tree.on_error

        async def _check(interaction: discord.Interaction) -> bool:
            if previous_check is not None:
                ok = await discord.utils.maybe_coroutine(previous_check, interaction)
                if not ok:
                    return False
            return await self._killswitch_interaction_check(interaction)

        async def _on_error(
            interaction: discord.Interaction, error: app_commands.AppCommandError
        ) -> None:
            if isinstance(error, KillswitchActive):
                msg = str(error) or "Kill switch is on."
                try:
                    if not interaction.response.is_done():
                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await interaction.followup.send(msg, ephemeral=True)
                except discord.HTTPException:
                    logger.warning("Could not send kill-switch block message", exc_info=True)
                return
            if previous_error is not None:
                await discord.utils.maybe_coroutine(previous_error, interaction, error)

        self._previous_check = previous_check
        self._previous_error = previous_error
        tree.interaction_check = _check  # type: ignore[method-assign]
        tree.on_error = _on_error  # type: ignore[method-assign]
        self._installed = True

    def _restore_tree_hooks(self) -> None:
        if not self._installed:
            return
        tree = self.bot.tree
        if self._previous_check is not None:
            tree.interaction_check = self._previous_check  # type: ignore[method-assign]
        if self._previous_error is not None:
            tree.on_error = self._previous_error  # type: ignore[method-assign]
        self._installed = False

    async def _killswitch_interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self._enabled:
            return True
        if interaction_command_name(interaction) == "killswitch":
            return True
        raise KillswitchActive(
            "Kill switch is on — only `/killswitch off` is available."
        )

    @app_commands.command(
        name="killswitch",
        description="Owner: turn the bot kill switch on or off.",
    )
    @app_commands.describe(mode="on blocks all other slash commands; off restores them")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="on", value="on"),
            app_commands.Choice(name="off", value="off"),
        ]
    )
    async def killswitch(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ) -> None:
        owner_id = killswitch_owner_user_id()
        if owner_id is None:
            await interaction.response.send_message(
                "Kill switch owner is not configured (`RESTART_NOTIFY_USER_ID`).",
                ephemeral=True,
            )
            return
        if interaction.user.id != owner_id:
            await interaction.response.send_message(
                "Only the configured owner can use `/killswitch`.",
                ephemeral=True,
            )
            return

        want_on = mode.value == "on"
        if want_on == self._enabled:
            state = "on" if self._enabled else "off"
            await interaction.response.send_message(
                f"Kill switch is already **{state}**.",
                ephemeral=True,
            )
            return

        if not await self._persist(want_on):
            if want_on:
                await interaction.response.send_message(
                    "Could not save kill switch state — it remains **off**.",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "Could not save kill switch state — it remains **on**.",
                    ephemeral=True,
                )
            return

        if want_on:
            await interaction.response.send_message(
                "Kill switch **on** — the bot will ignore all slash commands except "
                "`/killswitch off`.",
                ephemeral=True,
            )
            logger.warning("Kill switch enabled by user %s", interaction.user.id)
        else:
            await interaction.response.send_message(
                "Kill switch **off** — slash commands are available again.",
                ephemeral=True,
            )
            logger.warning("Kill switch disabled by user %s", interaction.user.id)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(KillswitchCog(bot))
