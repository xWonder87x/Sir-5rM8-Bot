import asyncio
import discord
import os
from discord import app_commands
from discord.ext import tasks, commands
from dotenv import load_dotenv
from utils import config

# Initialize the bot (message_content not needed for slash commands)
intents = discord.Intents.default()

# Initialize the bot with proper intents
bot = commands.Bot(command_prefix='!', intents=intents)

async def load_extensions():
    await bot.load_extension('commands.general')
    await bot.load_extension('commands.server')
    await bot.load_extension('commands.admin')
    await bot.load_extension('commands.rates')
    await bot.load_extension('cogs.ratecheck')
    

@tasks.loop(minutes=5)
async def update_presence():
    """Periodically update the bot's rich presence."""
    activity = discord.Game(name="Dynamic Rates Monitoring")
    await bot.change_presence(activity=activity)

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

# Add this to your main.py

@bot.command()
@commands.is_owner()
async def sync(ctx):
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} command(s).")

load_dotenv()

async def main():
    await load_extensions()
    await bot.start(os.getenv('TOKEN'))

asyncio.run(main())