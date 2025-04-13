import discord
import json
from discord.ext import commands, tasks
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

class ExpCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_counts = defaultdict(int)  # Tracks XP for each user
        self.giveaway_channel = None
        self.giveaway_role = None
        self.giveaway_start_time = None  # Tracks when the giveaway started
        self.data_file = Path("data/exp_data.json")  # Path to the JSON file
        self.settings_file = Path("data/giveaway_settings.json")  # Path to the giveaway settings file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory exists
        self.load_data()  # Load XP data from the file
        self.giveaway_task.start()

    def save_data(self):
        """Save the XP data to a JSON file."""
        with self.data_file.open("w") as f:
            json.dump(self.message_counts, f)

    def load_data(self):
        """Load the XP data from a JSON file."""
        if self.data_file.exists():
            try:
                with self.data_file.open("r") as f:
                    self.message_counts.update(json.load(f))
            except json.JSONDecodeError:
                print("JSONDecodeError: The data file is empty or corrupted. Resetting XP data.")
                self.message_counts.clear()
                self.save_data()  # Save an empty JSON object to reset the file

    def save_settings(self):
        """Save the giveaway settings to a JSON file."""
        settings = {
            "giveaway_channel": self.giveaway_channel.id if self.giveaway_channel else None,
            "giveaway_role": self.giveaway_role.id if self.giveaway_role else None,
            "giveaway_start_time": self.giveaway_start_time.isoformat() if self.giveaway_start_time else None,
        }
        with self.settings_file.open("w") as f:
            json.dump(settings, f)

    async def load_settings(self):
        """Load the giveaway settings from a JSON file."""
        if self.settings_file.exists():
            try:
                with self.settings_file.open("r") as f:
                    settings = json.load(f)
                    if settings.get("giveaway_channel"):
                        self.giveaway_channel = self.bot.get_channel(settings["giveaway_channel"])
                    if settings.get("giveaway_role"):
                        # Wait until the bot is ready to access guilds
                        guild = self.bot.guilds[0] if self.bot.guilds else None
                        if guild:
                            self.giveaway_role = guild.get_role(settings["giveaway_role"])
                    if settings.get("giveaway_start_time"):
                        self.giveaway_start_time = datetime.fromisoformat(settings["giveaway_start_time"])
            except json.JSONDecodeError:
                print("JSONDecodeError: The settings file is empty or corrupted. Resetting giveaway settings.")
                self.giveaway_channel = None
                self.giveaway_role = None
                self.giveaway_start_time = None
                self.save_settings()  # Save default settings

    @commands.Cog.listener()
    async def on_ready(self):
        """Ensure settings are loaded after the bot is ready."""
        await self.load_settings()

    @commands.command(name="list_exp", help="List all users and their XP")
    async def list_exp(self, ctx):
        """Command to list all users and their XP."""
        if not self.message_counts:
            await ctx.send("No XP data available.")
            return

        # Format the XP data into a readable list
        exp_list = []
        for user_id, xp in self.message_counts.items():
            user = self.bot.get_user(int(user_id))
            username = user.name if user else f"User ID {user_id}"
            exp_list.append(f"{username}: {xp} XP")

        # Send the list as a message
        await ctx.send("**XP Leaderboard:**\n" + "\n".join(exp_list))

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignore bot messages
        self.message_counts[str(message.author.id)] += 1  # Increment XP for the user
        self.save_data()  # Save data after every change

    @commands.command(name="start_giveaway", help="Start a giveaway in a specific channel")
    @commands.has_permissions(administrator=True)
    async def start_giveaway(self, ctx, channel: discord.TextChannel, role: discord.Role):
        self.giveaway_channel = channel
        self.giveaway_role = role
        self.giveaway_start_time = datetime.utcnow()  # Record the start time
        self.save_settings()  # Save the settings to the file
        await ctx.send(f"Giveaway started in {channel.mention} and will ping {role.mention} every hour.")

    @tasks.loop(hours=1)
    async def giveaway_task(self):
        if self.giveaway_channel and self.giveaway_role:
            if self.message_counts:
                # Find the user with the most XP
                top_user_id = max(self.message_counts, key=self.message_counts.get)
                top_user_xp = self.message_counts[top_user_id]
                top_user = self.bot.get_user(int(top_user_id))

                # Announce the winner
                await self.giveaway_channel.send(
                    f"{self.giveaway_role.mention} The user with the most XP this hour is {top_user.mention} with {top_user_xp} XP!"
                )

                # Reset the XP counts
                self.message_counts.clear()
                self.save_data()  # Save the reset data
            else:
                await self.giveaway_channel.send("No messages were sent this hour.")

    @commands.command(name="time_left", help="Check how much time is left for the giveaway")
    async def time_left(self, ctx):
        """Command to check how much time is left for the giveaway."""
        if not self.giveaway_start_time:
            await ctx.send("No giveaway is currently running.")
            return

        # Calculate the time elapsed since the giveaway started
        elapsed_time = datetime.utcnow() - self.giveaway_start_time
        time_left = timedelta(hours=1) - elapsed_time

        if time_left.total_seconds() > 0:
            await ctx.send(f"Time left for the current giveaway: {time_left}.")
        else:
            await ctx.send("The current giveaway period has ended.")

    @giveaway_task.before_loop
    async def before_giveaway_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ExpCount(bot))