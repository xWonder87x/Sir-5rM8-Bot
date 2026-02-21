import asyncio
import sys

import discord
from discord.ext import tasks, commands

from utils import config

intents = discord.Intents.default()
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
    activity = discord.Game(name=f"In {count} server{'s' if count != 1 else ''}")
    await bot.change_presence(activity=activity)


@update_presence.before_loop
async def before_update_presence():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        ratecheck_cog = bot.get_cog('RateCheckCog')
        if ratecheck_cog:
            ratecheck_cog.ratecheck.start()  # Start the background task
        # Start the presence update task
        update_presence.start()
    except Exception as e:
        print(f"Error syncing commands: {e}")


async def main():
    if not config.TOKEN:
        raise ValueError("TOKEN not set. Add TOKEN=your_bot_token to .env")
    await load_extensions()
    await bot.start(config.TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("Shutting down...")
        sys.exit(0)