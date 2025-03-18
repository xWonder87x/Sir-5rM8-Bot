import asyncio
import discord
import functions
import os
import random
import requests
import re
from discord.ext import tasks, commands
from discord import Interaction, User, TextChannel, Role, app_commands
from dotenv import load_dotenv
import commands as rate_commands  # Import the rate commands module

# Enable message content intent
intents = discord.Intents.default()
intents.message_content = True

# Initialize the bot with proper intents
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        ratecheck.start()  # Start the background task
    except Exception as e:
        print(e)

@bot.command()
async def say(ctx, *, message: str):
    await ctx.send(message)

load_dotenv()
my_secret = os.environ['TOKEN']

# ASA Server search
server_url = 'https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json'
rate_url = "https://cdn2.arkdedicated.com/asa/dynamicconfig.ini"

# Set server rates auto update channel and role 
@bot.tree.command(name="set_rate_channel",description="set channel for rate updates")
@app_commands.describe(channel="channel")
@app_commands.describe(role="role")
@app_commands.checks.has_permissions(administrator=True)
async def set_rate_channel(int:discord.Integration,channel:TextChannel,role:Role):
    functions.add_server_channel(str(int.guild.id),str(channel.id),str(role.id))
    await channel.send("This channel is been set for automatic Official PVE rates updates.")
    await int.response.send_message(f"{channel.mention} is set for automatic Official PVE rates updates.")

@bot.tree.error
async def on_app_commandError(int:discord.Interaction,error):
    await int.response.send_message(error,ephemeral=True)

# Server status command
@bot.tree.command(name="serverstatus", description="Checks the server status")
@app_commands.describe(server="Server Number")
async def serverstatus(interaction: discord.Interaction, server: str):
    await interaction.response.send_message(f"Searching for {server}\n-------------------------------")
    result = functions.find_server(server)
    await interaction.channel.send(result)

# Summon command
@bot.tree.command(name="summon", description="Summon a user via DM")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(to_user="User to summon")
async def summon(interaction: discord.Interaction, to_user: User):
    await to_user.create_dm()
    chan = interaction.channel
    await to_user.send(f"Your presence is requested in: {chan.mention}")
    await interaction.response.send_message(f"Message has been sent to {to_user.mention} successfully!", ephemeral=True)

# Summon command error handling
@summon.error
async def summon_error(interaction: discord.Interaction, error):
    await interaction.response.send_message("<a:alert:932990503258054677> You don't have permissions to use this command!", ephemeral=True)

# Rate check task loop (runs every 1 minute)
@tasks.loop(minutes=1)
async def ratecheck():
    serverlist, data, flag = functions.loop()
    if flag == 0:
        pattern = r"^\s*([\w.]+)\s*=\s*([\w.-]+)\s*$"
        values = []
        for line in data.split('\n'):
            match = re.match(pattern, line)
            if match:
                values.append(match.groups()[1])

        for ent in serverlist:
            try:
                guild = bot.get_guild(int(ent['server_id']))
                channel = guild.get_channel(int(ent['channel_id']))
                role = guild.get_role(int(ent['role']))
                emb = discord.Embed(
                    title='ASA Official Server Rates',
                    description="",
                    colour=discord.Colour.pink()
                )
                emb.set_thumbnail(url='https://ark.wiki.gg/images/thumb/0/0a/ASA_Logo_transparent.png/198px-ASA_Logo_transparent.png')
                emb.add_field(name=f"**✨ `{values[2]}x` EXP**", value='', inline=False)
                emb.add_field(name=f"**🌴 `{values[1]}x` Harvesting**", value='', inline=False)
                emb.add_field(name=f"**🦖 `{values[0]}x` Taming**", value='', inline=False)
                emb.add_field(name=f"**💞 `{values[3]}x` Mating Interval**", value='', inline=False)
                emb.add_field(name=f"**🐣 `{values[5]}x` Egg Hatch**", value='', inline=False)
                emb.add_field(name=f"**🐤 `{values[4]}x` Baby Mature**", value='', inline=False)
                emb.add_field(name=f"**🤗 `{values[7]}x` Imprint**", value='', inline=False)
                emb.add_field(name=f"**🤗 `{values[6]}x` Cuddle Interval**", value='', inline=False)
                await channel.send(embed=emb)
                await channel.send(f"The {role.mention} have changed!")
            except KeyError:
                print("Server channel missing or something else went wrong!")

bot.run(my_secret)