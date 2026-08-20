"""Official in-game ASA notifications (notification.html) → Discord channels."""
from __future__ import annotations

import db
from functions.asa_cache import current_announcement


def consume_ark_notice_update() -> tuple[str | None, list[dict]]:
    """
    Compare the cached official notice to the last posted text.
    First run seeds state and does not post (avoids spam on restart).
    Empty pages (``..``) are stored but not posted.
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
    if not current:
        return None, []
    return current, db.get_ark_notification_channels()
