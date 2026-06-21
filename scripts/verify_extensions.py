#!/usr/bin/env python3
"""Load every extension into a bare Bot — no Discord token required."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["EXTENSION_VERIFY"] = "1"

import discord
from discord.ext import commands

from commands.core.extensions import COG_EXTENSIONS, load_all_extensions


async def main() -> int:
    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)
    try:
        await load_all_extensions(bot)
    except Exception:
        return 1

    names = [cmd.name for cmd in bot.tree.get_commands()]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        print(f"Duplicate slash command names: {sorted(dupes)}", file=sys.stderr)
        return 1

    print(f"Loaded {len(COG_EXTENSIONS)} extension(s), {len(names)} slash command(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
