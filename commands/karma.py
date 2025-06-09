import discord
from discord.ext import commands
from discord import app_commands
import datetime
import json
import os

# In-memory storage for demonstration; replace with persistent storage for production
user_karma = {}
user_cooldowns = {}

COOLDOWN_HOURS = 24
LOG_FILE = "karma_log.json"
BALANCE_FILE = "karma_balancesheet.json"

def log_karma_action(action, user_id, target_id=None, amount=0, result=None):
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "action": action,
        "user_id": user_id,
        "target_id": target_id,
        "amount": amount,
        "result": result
    }
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
    data.append(log_entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def update_karma_balance(user: discord.Member, action: str, amount: int, by: discord.Member):
    # Load or create the balance file
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "r", encoding="utf-8") as f:
            balances = json.load(f)
    else:
        balances = {}

    user_id = str(user.id)
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "action": action,
        "amount": amount,
        "by": by.display_name
    }

    # Ensure user entry exists
    if user_id not in balances:
        balances[user_id] = {
            "name": user.display_name,
            "history": []
        }
    balances[user_id]["name"] = user.display_name  # Update name in case it changed
    balances[user_id]["history"].append(entry)
    # Keep only the last 10 actions
    balances[user_id]["history"] = balances[user_id]["history"][-10:]

    with open(BALANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, indent=2)

class Karma(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="send-karma", description="Send 1 karma to another user (24h cooldown)")
    @app_commands.describe(member="The user you want to send karma to")
    async def send_karma(self, interaction: discord.Interaction, member: discord.Member):
        giver_id = interaction.user.id
        receiver_id = member.id

        if giver_id == receiver_id:
            await interaction.response.send_message("You can't send karma to yourself!", ephemeral=True)
            log_karma_action("send-karma-failed-self", giver_id, receiver_id, 0, "self")
            return

        now = datetime.datetime.utcnow()
        last_given = user_cooldowns.get(giver_id)

        if last_given and (now - last_given).total_seconds() < COOLDOWN_HOURS * 3600:
            remaining = COOLDOWN_HOURS * 3600 - (now - last_given).total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(
                f"You must wait {hours}h {minutes}m before sending karma again.",
                ephemeral=True
            )
            log_karma_action("send-karma-failed-cooldown", giver_id, receiver_id, 0, f"{hours}h {minutes}m left")
            return

        user_karma[receiver_id] = user_karma.get(receiver_id, 0) + 1
        user_cooldowns[giver_id] = now

        await interaction.response.send_message(
            f"{member.mention} received 1 karma! Total karma: {user_karma[receiver_id]}"
        )
        log_karma_action("send-karma", giver_id, receiver_id, 1, user_karma[receiver_id])
        update_karma_balance(member, "add", 1, interaction.user)

    @app_commands.command(name="karma", description="Check how much karma you have")
    async def karma(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        karma = user_karma.get(user_id, 0)
        await interaction.response.send_message(
            f"You have {karma} karma."
        )
        log_karma_action("check-karma", user_id, None, 0, karma)

    @app_commands.command(name="take-karma", description="Remove 1 karma from a user (admin only)")
    @app_commands.describe(member="The user you want to take karma from")
    @app_commands.checks.has_permissions(administrator=True)
    async def take_karma(self, interaction: discord.Interaction, member: discord.Member):
        user_id = member.id
        if user_karma.get(user_id, 0) > 0:
            user_karma[user_id] -= 1
            await interaction.response.send_message(
                f"Took 1 karma from {member.mention}. Total karma: {user_karma[user_id]}"
            )
            log_karma_action("take-karma", interaction.user.id, user_id, -1, user_karma[user_id])
            update_karma_balance(member, "remove", -1, interaction.user)
        else:
            await interaction.response.send_message(
                f"{member.mention} has no karma to take."
            )
            log_karma_action("take-karma-failed", interaction.user.id, user_id, 0, "no karma")

    @app_commands.command(name="karma-check", description="Check how much karma another user has")
    @app_commands.describe(member="The user whose karma you want to check")
    async def karma_check(self, interaction: discord.Interaction, member: discord.Member):
        user_id = member.id
        karma = user_karma.get(user_id, 0)
        await interaction.response.send_message(
            f"{member.display_name} has {karma} karma."
        )
        log_karma_action("check-other-karma", interaction.user.id, user_id, 0, karma)

    @app_commands.command(name="karma-log", description="Show the last 10 karma adds/removals for a user")
    @app_commands.describe(member="The user whose karma log you want to see")
    async def karma_log(self, interaction: discord.Interaction, member: discord.Member):
        user_id = str(member.id)
        if os.path.exists(BALANCE_FILE):
            with open(BALANCE_FILE, "r", encoding="utf-8") as f:
                balances = json.load(f)
        else:
            balances = {}

        if user_id not in balances or not balances[user_id]["history"]:
            await interaction.response.send_message(
                f"No karma history found for {member.display_name}.", ephemeral=True
            )
            return

        history = balances[user_id]["history"][-10:]
        lines = []
        for entry in history:
            action = "Added" if entry["amount"] > 0 else "Removed"
            lines.append(
                f'`{entry["timestamp"]}`: {action} {abs(entry["amount"])} by {entry["by"]}'
            )
        msg = f"Last {len(lines)} karma actions for **{member.display_name}**:\n" + "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Karma(bot))