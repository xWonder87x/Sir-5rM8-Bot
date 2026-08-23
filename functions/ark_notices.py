"""Official in-game ASA notifications (notification.html) → Discord channels."""
from __future__ import annotations

import re

import db
from functions import json_db_cache as cache
from functions.asa_cache import current_announcement

_EXECSAVE_RE = re.compile(r"^execsave[.!]*$", re.IGNORECASE)
_COUNTDOWN_RE = re.compile(
    r"\b(?:15|10|5)\s*(?:minutes?|mins?)\b",
    re.IGNORECASE,
)


def is_execsave_notice(text: str) -> bool:
    """True when the official page is only the in-game ``execsave`` line."""
    compact = " ".join((text or "").split()).strip()
    return bool(compact) and bool(_EXECSAVE_RE.fullmatch(compact))


def is_restart_countdown_notice(text: str) -> bool:
    """True for the usual 15 / 10 / 5 minute restart warnings."""
    return bool(_COUNTDOWN_RE.search(text or ""))


def consume_ark_notice_update() -> tuple[str | None, list[dict]]:
    """
    Compare the cached official notice to the last posted text.
    First run seeds state and does not post (avoids spam on restart).
    Empty pages (``..``) and ``execsave`` are stored but not posted.
    Returns (text, channels) when guilds should be notified.
    """
    announcement = current_announcement()
    if announcement is None or not announcement.fetch_ok:
        return None, []
    current = announcement.text or ""
    previous = cache.get("ark_notice_state", db.get_previous_ark_notice)
    if previous is None:
        db.save_previous_ark_notice(current)
        cache.put("ark_notice_state", current)
        return None, []
    if current == previous:
        return None, []
    # A changed notice is the only normal-time read-back from Neon.  Prefer
    # the authoritative value if another process changed it meanwhile.
    verified_previous = db.get_previous_ark_notice()
    if verified_previous is not None:
        previous = verified_previous
    db.save_previous_ark_notice(current)
    cache.put("ark_notice_state", current)
    if not current or is_execsave_notice(current):
        return None, []
    return current, cache.get("ark_notifications", db.get_ark_notification_channels)


def get_ark_notification(guild_id: str) -> dict | None:
    channels = cache.get("ark_notifications", db.get_ark_notification_channels)
    for row in channels:
        if str(row.get("guild_id")) == str(guild_id):
            return {
                "channel_id": row.get("channel_id"),
                "last_message_id": row.get("last_message_id"),
            }
    return None


def set_ark_notice_last_message(guild_id: str, message_id: str | None) -> None:
    db.set_ark_notice_last_message(guild_id, message_id)
    channels = cache.get("ark_notifications", db.get_ark_notification_channels)
    for row in channels:
        if str(row.get("guild_id")) == str(guild_id):
            row["last_message_id"] = message_id
            break
    cache.put("ark_notifications", channels)


def set_ark_notification(guild_id: str, channel_id: str) -> None:
    db.set_ark_notification(guild_id, channel_id)
    channels = cache.get("ark_notifications", db.get_ark_notification_channels)
    existing = next(
        (row for row in channels if str(row.get("guild_id")) == str(guild_id)),
        None,
    )
    if existing is None:
        channels.append(
            {"guild_id": str(guild_id), "channel_id": str(channel_id), "last_message_id": None}
        )
    else:
        existing["last_message_id"] = (
            existing.get("last_message_id") if existing.get("channel_id") == str(channel_id) else None
        )
        existing["channel_id"] = str(channel_id)
    cache.put("ark_notifications", channels)


def clear_ark_notification(guild_id: str) -> bool:
    cleared = db.clear_ark_notification(guild_id)
    if cleared:
        channels = cache.get("ark_notifications", db.get_ark_notification_channels)
        cache.put(
            "ark_notifications",
            [row for row in channels if str(row.get("guild_id")) != str(guild_id)],
        )
    return cleared


def verify_cached_ark_state() -> dict[str, bool]:
    result = {
        "ark_notice_state": cache.verify("ark_notice_state", db.get_previous_ark_notice),
        "ark_notifications": cache.verify(
            "ark_notifications", db.get_ark_notification_channels
        ),
    }
    return result
