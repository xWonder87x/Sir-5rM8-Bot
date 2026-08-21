"""Official in-game ASA notifications (notification.html) → Discord channels."""
from __future__ import annotations

import re

import db
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
    previous = db.get_previous_ark_notice()
    if previous is None:
        db.save_previous_ark_notice(current)
        return None, []
    if current == previous:
        return None, []
    db.save_previous_ark_notice(current)
    if not current or is_execsave_notice(current):
        return None, []
    return current, db.get_ark_notification_channels()
