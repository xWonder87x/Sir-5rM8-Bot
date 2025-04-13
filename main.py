import asyncio
import discord
import os
import json
from discord.ext import tasks, commands
from dotenv import load_dotenv
from utils import functions, config

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot with proper intents
bot = commands.Bot(command_prefix='!', intents=intents)

async def load_extensions():
    await bot.load_extension('commands.general')
    await bot.load_extension('commands.admin')
    await bot.load_extension('commands.rates')
    await bot.load_extension("commands.exp_count")
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

def load_data(self):
    """Load the XP data from a JSON file."""
    self.data_file.parent.mkdir(parents=True, exist_ok=True)
    if self.data_file.exists():
        try:
            with self.data_file.open("r") as f:
                self.message_counts.update(json.load(f))
        except json.JSONDecodeError:
            print("JSONDecodeError: The data file is empty or corrupted. Resetting XP data.")
            self.message_counts.clear()
            self.save_data()  # Save an empty JSON object to reset the file

load_dotenv()

async def main():
    await load_extensions()
    await bot.start(os.getenv('TOKEN'))

asyncio.run(main())