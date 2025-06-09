import asyncio
import discord
import os
import json
from discord import app_commands
from discord.ext import tasks, commands
from dotenv import load_dotenv
from utils import functions, config

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot with proper intents
bot = commands.Bot(command_prefix='!', intents=intents)

#server status command
@bot.tree.command(name="serverstatus", description="Checks the server status")
@app_commands.describe(server="Server Number")
async def serverstatus(int: discord.Interaction,server:str):
   await int.response.send_message(f"Searching for {server}\n-------------------------------")
   result=functions.find_server(server)
   await int.channel.send(result)

async def load_extensions():
    await bot.load_extension('commands.general')
    await bot.load_extension('commands.admin')
    await bot.load_extension('commands.rates')
    await bot.load_extension("commands.exp_count")
    await bot.load_extension('cogs.ratecheck')
    await bot.load_extension('commands.karma')
    

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