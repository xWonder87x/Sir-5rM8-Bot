"""Bothunter message templates and action helpers (ported from RiskyMH/honeypot)."""
from __future__ import annotations

from typing import Literal

BothunterAction = Literal["softban", "ban", "disabled"]

ACTION_TEXT = {
    "ban": "an immediate ban",
    "softban": "a softban",
    "disabled": "no action (bothunter is disabled)",
}
ACTION_PAST = {
    "ban": "banned",
    "softban": "kicked",
    "disabled": "flagged",
}
ACTION_LABEL = {
    "ban": "Bans",
    "softban": "Kicks",
    "disabled": "Triggers",
}

DEFAULT_WARNING = (
    "## DO NOT SEND MESSAGES IN THIS CHANNEL\n\n"
    "This channel is used to catch spam bots. Any messages sent here will result in "
    "**{{action:text}}**."
)

DEFAULT_DM = (
    "## Bothunter Triggered\n\n"
    "Hey {{user:mention}}, you have been **{{action:text}}** from **{{server:name}}** "
    "for sending a message in the [bothunter]({{bothunter:channel:link}}) channel.\n\n"
    "This may have happened if someone gained access to your account through malware, "
    "stolen sessions or leaked passwords. Please recover your account, scan your device, "
    "and change your passwords."
)

DEFAULT_DM_REINVITE = "\n\nYou can rejoin via {{reinvite:link}}"

DEFAULT_LOG = (
    "{{user:mention}} was {{action:text}} for triggering the bothunter in "
    "{{bothunter:channel:mention}}\n-# User ID: `{{user:id}}`"
)

VALID_EXPERIMENTS = frozenset({
    "no-dm",
    "no-warning-msg",
    "timeout-first",
    "only-recent-delete",
    "reinvite",
})


def normalize_action(action: str | None) -> BothunterAction:
    if action in ("ban", "softban", "disabled"):
        return action  # type: ignore[return-value]
    if action == "kick":
        return "softban"
    return "softban"


def normalize_experiments(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    out: list[str] = []
    for item in raw:
        if item in VALID_EXPERIMENTS and item not in out:
            out.append(item)
    return out


def _replace(template: str, mapping: dict[str, str]) -> str:
    text = template
    for key, value in mapping.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def warning_content(moderated_count: int, action: BothunterAction, custom: str | None = None) -> str:
    action_text = ACTION_TEXT.get(action, ACTION_TEXT["softban"])
    label = ACTION_LABEL.get(action, "Triggers")
    body = custom or DEFAULT_WARNING
    body = _replace(body, {
        "action": action_text,
        "action:text": action_text,
        "bothunter:moderation-count": f"{moderated_count:,}",
        "honeypot:moderation-count": f"{moderated_count:,}",
    })
    return f"{body}\n\n-# {label}: {moderated_count:,}"


def dm_content(
    *,
    user_id: str,
    action: BothunterAction,
    guild_name: str,
    channel_link: str,
    reinvite_url: str | None,
    custom: str | None = None,
    include_reinvite_default: bool = False,
) -> str:
    past = ACTION_PAST.get(action, "removed")
    template = custom or DEFAULT_DM
    if not custom and include_reinvite_default and reinvite_url:
        template += DEFAULT_DM_REINVITE
    return _replace(template, {
        "user:mention": f"<@{user_id}>",
        "user:ping": f"<@{user_id}>",
        "user:id": user_id,
        "action": past,
        "action:text": past,
        "server:name": guild_name,
        "server:name:linked": guild_name,
        "bothunter:channel:link": channel_link,
        "honeypot:channel:link": channel_link,
        "reinvite:link": reinvite_url or "*<invite link not available>*",
    })


def log_content(
    *,
    user_id: str,
    username: str,
    channel_id: str,
    action: BothunterAction,
    moderated_count: int,
    custom: str | None = None,
) -> str:
    past = ACTION_PAST.get(action, "removed")
    mention = f"<@{user_id}>"
    channel_mention = f"<#{channel_id}>"
    template = custom or DEFAULT_LOG
    return _replace(template, {
        "user:id": user_id,
        "user": mention,
        "user:ping": mention,
        "user:mention": mention,
        "user:name": username or user_id,
        "user:global-name": username or user_id,
        "action": past,
        "action:text": past,
        "bothunter:channel": channel_mention,
        "bothunter:channel:mention": channel_mention,
        "bothunter:channel:ping": channel_mention,
        "honeypot:channel": channel_mention,
        "honeypot:channel:mention": channel_mention,
        "honeypot:channel:ping": channel_mention,
        "bothunter:moderation-count": f"{moderated_count:,}",
        "honeypot:moderation-count": f"{moderated_count:,}",
    })


def default_config(guild_id: str) -> dict:
    return {
        "guild_id": str(guild_id),
        "channel_id": None,
        "log_channel_id": None,
        "action": "softban",
        "warning_msg_id": None,
        "experiments": [],
        "warning_message": None,
        "dm_message": None,
        "log_message": None,
        "reinvite_code": None,
    }
