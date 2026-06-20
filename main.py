from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
import time

import discord
from discord.ext import tasks, commands

from utils import config

# Configure logging: both file and console
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
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def load_extensions():
    await bot.load_extension('commands.help')
    await bot.load_extension('commands.server')
    await bot.load_extension('commands.karma')
    await bot.load_extension('commands.admin')
    await bot.load_extension('commands.rates')
    await bot.load_extension('cogs.ratecheck')


@tasks.loop(minutes=5)
async def update_presence():
    """Periodically update the bot's rich presence with server count."""
    count = len(bot.guilds)
    activity = discord.Game(name=f"Watching over {count} server{'s' if count != 1 else ''}")
    await bot.change_presence(activity=activity)


@update_presence.before_loop
async def before_update_presence():
    await bot.wait_until_ready()


def _can_reload(ctx):
    """Allow bot owner or server administrators."""
    if ctx.bot.owner_id and ctx.author.id == ctx.bot.owner_id:
        return True
    if getattr(ctx.bot, "owner_ids", None) and ctx.author.id in ctx.bot.owner_ids:
        return True
    if ctx.guild and ctx.author.guild_permissions.administrator:
        return True
    return False


def _start_background_tasks():
    """Start periodic tasks if they are not already running."""
    ratecheck_cog = bot.get_cog('RateCheckCog')
    if ratecheck_cog and not ratecheck_cog.ratecheck.is_running():
        ratecheck_cog.ratecheck.start()
    if not update_presence.is_running():
        update_presence.start()


@bot.command(name="reload")
@commands.check(_can_reload)
async def reload_all(ctx):
    """Reload all cogs and sync slash commands. Use after code changes to avoid full restart."""
    extensions = list(bot.extensions.keys())
    reload_ok = 0
    failed = []
    for ext in extensions:
        try:
            await bot.reload_extension(ext)
            reload_ok += 1
            logger.info("Reloaded %s", ext)
        except Exception as e:
            failed.append(f"{ext}: {e}")
            logger.exception("Failed to reload %s", ext)
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d slash commands.", len(synced))
    except Exception as e:
        failed.append(f"tree.sync: {e}")
        logger.exception("Failed to sync commands: %s", e)
    if failed:
        await ctx.send(f"Reloaded {reload_ok}/{len(extensions)} cogs. **Errors:**\n" + "\n".join(failed))
    else:
        await ctx.send(f"Reloaded all {len(extensions)} cogs and synced slash commands.")
    _start_background_tasks()


def _log_storage_backend():
    if config.USE_SUPABASE:
        logger.info("Storage backend: Supabase (%s)", config.SUPABASE_URL)
        try:
            from utils.storage_supabase import check_connection
            check_connection()
            logger.info("Supabase connection OK")
        except Exception as e:
            logger.error(
                "Supabase connection failed: %s. "
                "Check SUPABASE_URL (https://YOUR_PROJECT.supabase.co) and SUPABASE_SERVICE_KEY. "
                "Remove both env vars to fall back to JSON files in data/.",
                e,
            )
    else:
        logger.info("Storage backend: JSON files (%s)", config.DATA_DIR)


@bot.event
async def on_ready():
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    _log_storage_backend()
    try:
        synced = await bot.tree.sync()
        logger.info("Synced %d command(s)", len(synced))
        _start_background_tasks()
    except Exception as e:
        logger.exception("Error syncing commands: %s", e)


async def main():
    if not config.TOKEN:
        raise ValueError("TOKEN not set. Add TOKEN=your_bot_token to .env")
    await load_extensions()
    await bot.start(config.TOKEN)


# Retry on rate limit (429): wait then restart in a fresh process
MAX_LOGIN_RETRIES = 5
LOGIN_RETRY_WAIT = 120  # seconds

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