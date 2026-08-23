"""Hourly reconciliation of JSON cache copies against Neon."""
from __future__ import annotations

import asyncio
import logging
import os

from discord.ext import commands, tasks

from functions import verify_cached_db_state

logger = logging.getLogger(__name__)


class CacheSync(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if not os.environ.get("EXTENSION_VERIFY"):
            self.reconcile.start()

    def cog_unload(self) -> None:
        self.reconcile.cancel()

    @tasks.loop(hours=1)
    async def reconcile(self) -> None:
        try:
            result = await asyncio.to_thread(verify_cached_db_state)
            repaired = [name for name, equal in result.items() if not equal]
            if repaired:
                logger.warning("Hourly JSON cache reconciliation repaired: %s", ", ".join(repaired))
            else:
                logger.info("Hourly JSON cache reconciliation OK (%s cache(s))", len(result))
        except Exception:
            logger.exception("Hourly JSON cache reconciliation failed")

    @reconcile.before_loop
    async def before_reconcile(self) -> None:
        await self.bot.wait_until_ready()
        # Let persisted JSON copies serve the first hour after a restart.
        await asyncio.sleep(60 * 60)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CacheSync(bot))
