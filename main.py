from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
import time

import discord
from discord.ext import tasks, commands

import config
import db
from commands.core.command_sync import sync_application_commands
from commands.core.extensions import load_all_extensions

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
config.DATA_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(config.DATA_DIR / "bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

extensions_loaded = False
global_sync_ok = False


@tasks.loop(minutes=5)
async def update_presence():
    count = len(bot.guilds)
    activity = discord.Game(name=f"Watching over {count} server{'s' if count != 1 else ''}")
    await bot.change_presence(activity=activity)


@update_presence.before_loop
async def before_update_presence():
    await bot.wait_until_ready()


def _validate_env() -> None:
    if not config.TOKEN:
        logger.error("Missing required environment variable: TOKEN")
        sys.exit(1)

    if db.use_supabase():
        logger.info("Storage backend: Supabase (%s)", os.environ.get("SUPABASE_URL"))
        try:
            db.check_connection()
            logger.info("Supabase connection OK")
        except Exception as exc:
            logger.error(
                "Supabase connection failed: %s. "
                "Check SUPABASE_URL and credentials, or remove Supabase env vars "
                "to fall back to JSON files in %s.",
                exc,
                config.DATA_DIR,
            )
            sys.exit(1)

        for name, ok, err in db.check_schema():
            if ok:
                logger.info("Schema OK: %s", name)
            else:
                logger.error("Schema check failed for %s: %s", name, err)
                sys.exit(1)
    else:
        logger.info("Storage backend: JSON files (%s)", config.DATA_DIR)


def _start_background_tasks() -> None:
    if not update_presence.is_running():
        update_presence.start()


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    logger.exception("Unhandled prefix command error", exc_info=error)


@bot.event
async def on_ready():
    global extensions_loaded, global_sync_ok

    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)

    if not extensions_loaded:
        await load_all_extensions(bot)
        extensions_loaded = True
        try:
            await sync_application_commands(bot)
            global_sync_ok = True
        except Exception:
            logger.exception("Initial slash command sync failed")
        _start_background_tasks()
        return

    if not global_sync_ok:
        try:
            await sync_application_commands(bot)
            global_sync_ok = True
        except Exception:
            logger.exception("Retry slash command sync failed")

    _start_background_tasks()


async def main():
    _validate_env()
    await bot.start(config.TOKEN)


MAX_LOGIN_RETRIES = 5
LOGIN_RETRY_WAIT = 120

if __name__ == "__main__":
    attempt = int(os.environ.get("LOGIN_RETRY_ATTEMPT", "0"))
    if attempt >= MAX_LOGIN_RETRIES:
        logger.error("Max login retries (%s) reached. Exiting.", MAX_LOGIN_RETRIES)
        sys.exit(1)

    startup_delay = random.uniform(15, 45)
    if attempt > 0:
        startup_delay += 10 * attempt
    logger.info("Waiting %.0f seconds before login (staggered startup)...", startup_delay)
    time.sleep(startup_delay)

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down...")
        sys.exit(0)
    except discord.HTTPException as e:
        if e.status == 429 and attempt < MAX_LOGIN_RETRIES - 1:
            wait = min(600, LOGIN_RETRY_WAIT * (2 ** attempt))
            logger.warning(
                "Rate limited (429). Waiting %s seconds, then restarting for retry (%s/%s)...",
                wait, attempt + 1, MAX_LOGIN_RETRIES
            )
            time.sleep(wait)
            os.environ["LOGIN_RETRY_ATTEMPT"] = str(attempt + 1)
            os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:])
        else:
            raise
