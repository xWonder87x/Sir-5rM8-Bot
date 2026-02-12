"""
Orchestration layer: ASA API + storage.
Commands and cogs use this module.
"""
from utils import asa, constants, storage


def find_server(query: str) -> dict | None:
    """Search for an ASA server. Returns server dict or None."""
    return asa.find_server(query)


def fetch_current_rates() -> dict | None:
    """Fetch current ASA rates. Returns dict or None."""
    return asa.fetch_current_rates()


def add_server_channel(guild_id: str, channel_id: str, role_id: str) -> None:
    """Register a guild's rate notification channel and role."""
    storage.set_rate_notification(guild_id, channel_id, role_id)


def get_server_channel(guild_id: str) -> dict | None:
    """Get rate notification config for a guild."""
    return storage.get_rate_notification(guild_id)


def clear_server_channel(guild_id: str) -> bool:
    """Remove rate notification config for a guild."""
    return storage.clear_rate_notification(guild_id)


def karma_get_balance(user_id: str) -> int:
    return storage.karma_get_balance(user_id)


def karma_get_cooldown(giver_id: str, receiver_id: str):
    return storage.karma_get_cooldown(giver_id, receiver_id)


def karma_add(giver_id: str, receiver_id: str, giver_name: str, reason: str) -> int:
    return storage.karma_add(giver_id, receiver_id, giver_name, reason)


def karma_take(target_id: str, admin_id: str, admin_name: str) -> int | None:
    return storage.karma_take(target_id, admin_id, admin_name)


def karma_get_history(user_id: str) -> list:
    return storage.karma_get_history(user_id)


def karma_get_audit(limit: int = 20) -> list:
    return storage.karma_get_audit(limit)


def get_karma_settings() -> dict:
    return storage.get_karma_settings()


def check_rate_changes() -> tuple[list | None, dict | None, dict | None, int]:
    """
    Check if ASA rates have changed.
    Returns (server_list, current_rates, previous_rates, flag).
    flag=0: rates changed, send notifications. flag=1: no change.
    """
    current = asa.fetch_current_rates()
    if not current:
        return None, None, None, 1

    previous = storage.get_previous_rate_values()
    if previous is None:
        storage.save_previous_rate_values(current)
        return None, None, None, 1

    if any(previous.get(k) != current.get(k) for k in constants.RATE_KEYS):
        storage.save_previous_rate_values(current)
        server_list = storage.get_rate_notification_channels()
        return server_list, current, previous, 0

    return None, None, None, 1
