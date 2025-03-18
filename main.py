import asyncio
import discord
import os
from discord.ext import tasks, commands
from dotenv import load_dotenv
from utils import functions, config

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot with proper intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Load commands
bot.load_extension('commands.general')
bot.load_extension('commands.admin')
bot.load_extension('commands.rates')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        bot.get_cog('RateCheckCog').ratecheck.start()  # Start the background task
    except Exception as e:
        print(f"Error syncing commands: {e}")

load_dotenv()
bot.run(os.getenv('TOKEN'))