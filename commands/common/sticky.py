"""Reusable sticky-message manager.

Keeps a single bot-authored embed alive in a channel: remember its id (persisted
to ``data/*.json``), recover it after restarts by scanning channel history, edit
it in place when present, and re-post when missing.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, Optional

import discord

from .state import (
    clear_persisted_message_id,
    load_persisted_message_id,
    save_persisted_message_id,
)

logger = logging.getLogger("commands.common.sticky")

Matcher = Callable[[discord.Message, int], bool]
Pinner = Callable[[discord.Message], Awaitable[None]]


class StickyMessage:
    """Tracks one persistent embed in a channel."""

    def __init__(
        self,
        bot: discord.Client,
        *,
        state_path: Path,
        matcher: Matcher,
        log_label: str,
        pin: Optional[Pinner] = None,
        history_limit: int = 100,
    ) -> None:
        self.bot = bot
        self.state_path = state_path
        self.matcher = matcher
        self.log_label = log_label
        self._pin = pin
        self.history_limit = history_limit
        self.message_id: int | None = load_persisted_message_id(state_path)

    async def _try_pin(self, msg: discord.Message) -> None:
        if self._pin is not None:
            await self._pin(msg)

    async def recover(self, channel: discord.TextChannel) -> None:
        """Confirm the tracked id still exists, else find it by scanning history."""
        bot = self.bot.user
        if not bot:
            return
        if self.message_id:
            try:
                await channel.fetch_message(self.message_id)
                return
            except discord.NotFound:
                self.message_id = None
        async for msg in channel.history(limit=self.history_limit):
            if self.matcher(msg, bot.id):
                self.message_id = msg.id
                await asyncio.to_thread(
                    save_persisted_message_id, self.state_path, msg.id
                )
                return

    async def clear(self) -> None:
        """Forget the tracked id and remove the persisted state file."""
        self.message_id = None
        await asyncio.to_thread(clear_persisted_message_id, self.state_path)

    async def ensure(
        self,
        channel: discord.TextChannel,
        embed: discord.Embed,
        view: discord.ui.View | None = None,
    ) -> None:
        """Edit the sticky in place if present, otherwise post a fresh one."""
        await self.recover(channel)
        for _ in range(2):
            if not self.message_id:
                break
            try:
                msg = await channel.fetch_message(self.message_id)
                if view is not None:
                    await msg.edit(embed=embed, view=view)
                else:
                    await msg.edit(embed=embed)
                await self._try_pin(msg)
                return
            except discord.NotFound:
                self.message_id = None
                await self.recover(channel)
            except (discord.Forbidden, discord.HTTPException) as e:
                logger.warning("%s: could not edit info message: %s", self.log_label, e)
                return
        try:
            if view is not None:
                msg = await channel.send(embed=embed, view=view)
            else:
                msg = await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("%s: could not post info message: %s", self.log_label, e)
            return
        self.message_id = msg.id
        await asyncio.to_thread(save_persisted_message_id, self.state_path, msg.id)
        await self._try_pin(msg)
