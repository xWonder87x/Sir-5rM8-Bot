"""Stale-while-revalidate reconciliation of database cache copies."""
from __future__ import annotations

import asyncio
import logging
import os
import random

from discord.ext import commands, tasks

import config
from functions import verify_cached_db_state
from functions import json_db_cache as cache

logger = logging.getLogger(__name__)


def _run_reconciliation() -> tuple[dict[str, bool], dict, dict]:
    result = verify_cached_db_state()
    return result, cache.diagnostics_snapshot(), cache.stats_snapshot()


def _startup_delay() -> float:
    return config.JSON_CACHE_STARTUP_GRACE_SECONDS + random.uniform(
        0.0, config.JSON_CACHE_STARTUP_JITTER_SECONDS
    )


def _reconcile_interval() -> float:
    return config.JSON_CACHE_RECONCILE_SECONDS


class CacheSync(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if not os.environ.get("EXTENSION_VERIFY"):
            self.reconcile.change_interval(
                seconds=_reconcile_interval()
            )
            self.reconcile.start()

    def cog_unload(self) -> None:
        self.reconcile.cancel()

    @tasks.loop(seconds=60 * 60)
    async def reconcile(self) -> None:
        try:
            result, diagnostics, stats = await asyncio.to_thread(_run_reconciliation)
            repaired = [name for name, equal in result.items() if not equal]
            if repaired:
                logger.warning(
                    "JSON cache reconciliation repaired from database: %s",
                    ", ".join(repaired),
                )
            else:
                logger.info("JSON cache reconciliation OK (%s cache(s))", len(result))
            state = ", ".join(
                f"{name}={meta['source']}/{meta['age_seconds']:.1f}s"
                for name, meta in diagnostics.items()
            )
            logger.info("JSON cache state: %s; stats=%s", state or "empty", stats)
        except Exception:
            logger.exception("JSON cache reconciliation failed")

    @reconcile.before_loop
    async def before_reconcile(self) -> None:
        await self.bot.wait_until_ready()
        delay = _startup_delay()
        logger.info(
            "JSON cache startup grace %.1fs; database reconciliation remains authoritative",
            delay,
        )
        await asyncio.sleep(delay)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CacheSync(bot))
