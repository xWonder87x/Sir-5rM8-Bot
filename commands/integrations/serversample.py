"""Background sampler for ASA server player counts (feeds /serverstatus history)."""
from __future__ import annotations

import asyncio
import logging
import os

from discord.ext import commands, tasks

import config
import db
from functions.asa import _fetch_with_retry, server_key_from_server

logger = logging.getLogger(__name__)


class ServerSampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        minutes = max(int(config.SERVER_SAMPLE_INTERVAL_MINUTES), 1)
        self.sample_servers.change_interval(minutes=minutes)

    async def cog_load(self) -> None:
        if os.environ.get("EXTENSION_VERIFY"):
            return
        if not self.sample_servers.is_running():
            self.sample_servers.start()

    def cog_unload(self) -> None:
        self.sample_servers.cancel()

    def _sample_once(self) -> tuple[int, int]:
        """
        Fetch official list once and record samples for watched servers.
        Returns (recorded, pruned).
        """
        keys = db.list_watched_server_keys()
        if not keys:
            pruned = db.prune_server_samples()
            return 0, pruned

        resp = _fetch_with_retry(config.SERVER_LIST_URL)
        if not resp:
            logger.warning("Server sample skipped: official list fetch failed")
            return 0, 0

        by_key: dict[str, dict] = {}
        for server in resp.json():
            key = server_key_from_server(server)
            if key in keys:
                by_key[key] = server

        recorded = 0
        for key in keys:
            server = by_key.get(key)
            if not server:
                continue
            db.record_server_sample(
                key,
                int(server.get("NumPlayers") or 0),
                int(server.get("MaxPlayers") or 70),
            )
            recorded += 1

        pruned = db.prune_server_samples()
        return recorded, pruned

    @tasks.loop(minutes=5)
    async def sample_servers(self) -> None:
        try:
            recorded, pruned = await asyncio.to_thread(self._sample_once)
            if recorded or pruned:
                logger.info(
                    "Server samples: recorded=%s pruned=%s",
                    recorded,
                    pruned,
                )
        except Exception:
            logger.exception("Server sample loop failed")

    @sample_servers.before_loop
    async def before_sample_servers(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(ServerSampleCog(bot))
