"""Owner DMs when the bot is added to a Discord server."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import discord

import config

logger = logging.getLogger(__name__)

_DESC_MAX = 400
_FEATURE_MAX = 8


def _created_stamp(created_at: datetime | None) -> str:
    if created_at is None:
        return "—"
    ts = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    unix = int(ts.timestamp())
    return f"<t:{unix}:F> (<t:{unix}:R>)"


def _feature_list(guild: discord.Guild) -> str:
    features = [str(f).replace("_", " ").title() for f in (guild.features or [])]
    if not features:
        return "—"
    shown = features[:_FEATURE_MAX]
    extra = len(features) - len(shown)
    text = ", ".join(shown)
    if extra > 0:
        text += f" (+{extra} more)"
    return text


def _enum_label(value) -> str | None:
    if value is None:
        return None
    name = getattr(value, "name", None)
    raw = str(name) if name else str(value)
    return raw.replace("_", " ").title()


def build_guild_join_embed(
    guild: discord.Guild,
    *,
    owner: discord.abc.User | None = None,
    added_by: discord.abc.User | None = None,
    bot_guild_count: int | None = None,
) -> discord.Embed:
    owner = owner or getattr(guild, "owner", None)
    owner_id = getattr(owner, "id", None) or getattr(guild, "owner_id", None)
    if owner is not None:
        owner_value = f"{owner} (`{owner_id}`)"
    elif owner_id:
        owner_value = f"`{owner_id}`"
    else:
        owner_value = "—"

    added_value = "—"
    if added_by is not None:
        added_value = f"{added_by} (`{added_by.id}`)"

    description = (getattr(guild, "description", None) or "").strip()
    if len(description) > _DESC_MAX:
        description = description[: _DESC_MAX - 1] + "…"

    embed = discord.Embed(
        title="Added to a Discord server",
        description=guild.name or "Unknown server",
        colour=discord.Colour.green(),
    )
    icon = getattr(guild, "icon", None)
    icon_url = getattr(icon, "url", None) if icon is not None else None
    if icon_url:
        embed.set_thumbnail(url=icon_url)

    embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)
    embed.add_field(name="Members", value=str(getattr(guild, "member_count", None) or "—"), inline=True)
    embed.add_field(
        name="Boosts",
        value=f"Level {getattr(guild, 'premium_tier', 0) or 0} · {getattr(guild, 'premium_subscription_count', 0) or 0}",
        inline=True,
    )
    embed.add_field(name="Owner", value=owner_value, inline=False)
    embed.add_field(name="Added by", value=added_value, inline=False)
    embed.add_field(name="Created", value=_created_stamp(getattr(guild, "created_at", None)), inline=False)
    if description:
        embed.add_field(name="Description", value=description, inline=False)

    vanity = getattr(guild, "vanity_url_code", None)
    if vanity:
        embed.add_field(name="Vanity URL", value=f"https://discord.gg/{vanity}", inline=False)

    locale = getattr(guild, "preferred_locale", None)
    verification = _enum_label(getattr(guild, "verification_level", None))
    extra_bits = []
    if locale:
        extra_bits.append(str(locale))
    if verification:
        extra_bits.append(verification)
    text_n = len(getattr(guild, "text_channels", []) or [])
    voice_n = len(getattr(guild, "voice_channels", []) or [])
    extra_bits.append(f"{text_n} text / {voice_n} voice")
    embed.add_field(name="Locale · verification · channels", value=" · ".join(extra_bits), inline=False)
    embed.add_field(name="Features", value=_feature_list(guild), inline=False)

    footer = f"Now in {bot_guild_count} server{'s' if bot_guild_count != 1 else ''}" if bot_guild_count else None
    if footer:
        embed.set_footer(text=footer)
    return embed


async def _find_bot_adder(guild: discord.Guild) -> discord.abc.User | None:
    me = guild.me
    if me is None:
        return None

    async def scan() -> discord.abc.User | None:
        try:
            async for entry in guild.audit_logs(limit=8, action=discord.AuditLogAction.bot_add):
                target = entry.target
                if target is not None and getattr(target, "id", None) == me.id:
                    return entry.user
        except (discord.Forbidden, discord.HTTPException):
            return None
        return None

    found = await scan()
    if found:
        return found
    await asyncio.sleep(1.5)
    return await scan()


async def send_guild_join_dm(bot: discord.Client, guild: discord.Guild) -> None:
    notify_id = config.RESTART_NOTIFY_USER_ID
    if not notify_id:
        return

    owner = guild.owner
    if owner is None and guild.owner_id:
        try:
            owner = bot.get_user(guild.owner_id) or await bot.fetch_user(guild.owner_id)
        except (discord.NotFound, discord.HTTPException):
            owner = None

    added_by = await _find_bot_adder(guild)
    embed = build_guild_join_embed(
        guild,
        owner=owner,
        added_by=added_by,
        bot_guild_count=len(bot.guilds),
    )
    try:
        user = bot.get_user(int(notify_id)) or await bot.fetch_user(int(notify_id))
        await user.send(embed=embed)
        logger.info("Sent guild-join DM for %s (%s) to user %s", guild.name, guild.id, notify_id)
    except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
        logger.warning("Could not send guild-join DM to %s: %s", notify_id, exc)
