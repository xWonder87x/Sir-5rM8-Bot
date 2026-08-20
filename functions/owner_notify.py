"""Owner restart DMs and guild-join notices in the guild-list channel."""
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


async def get_owner_notify_channel(bot: discord.Client) -> discord.TextChannel | None:
    channel_id = config.GUILD_LIST_CHANNEL_ID
    if not channel_id:
        return None
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            logger.warning("Owner notify channel %s unavailable: %s", channel_id, exc)
            return None
    if not isinstance(channel, discord.TextChannel):
        logger.warning("Owner notify channel %s is not a text channel", channel_id)
        return None
    return channel


async def post_owner_notice(
    bot: discord.Client,
    *,
    content: str = "",
    embed: discord.Embed | None = None,
) -> bool:
    notify_id = config.RESTART_NOTIFY_USER_ID
    if not notify_id:
        return False
    channel = await get_owner_notify_channel(bot)
    if channel is None:
        logger.warning("Guild list channel is unset or unavailable; skipping owner notice")
        return False

    ping = f"<@{int(notify_id)}>"
    text = ping if not content else f"{ping} {content}"
    try:
        kwargs: dict = {
            "content": text,
            "allowed_mentions": discord.AllowedMentions(
                everyone=False,
                roles=False,
                users=[discord.Object(id=int(notify_id))],
            ),
        }
        if embed is not None:
            kwargs["embed"] = embed
        await channel.send(**kwargs)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        logger.warning("Could not post owner notice in %s: %s", channel.id, exc)
        return False


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


async def notify_guild_join(bot: discord.Client, guild: discord.Guild) -> None:
    if not config.RESTART_NOTIFY_USER_ID:
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
    if await post_owner_notice(bot, embed=embed):
        logger.info("Posted guild-join notice for %s (%s)", guild.name, guild.id)


async def notify_restart(bot: discord.Client, message: str) -> bool:
    notify_id = config.RESTART_NOTIFY_USER_ID
    if not notify_id:
        return False
    try:
        user = bot.get_user(int(notify_id)) or await bot.fetch_user(int(notify_id))
        if user is None:
            logger.warning("Could not resolve restart notify user %s", notify_id)
            return False
        await user.send(message)
        logger.info("Sent restart DM to user %s", notify_id)
        return True
    except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
        logger.warning("Could not send restart DM to %s: %s", notify_id, exc)
        return False
