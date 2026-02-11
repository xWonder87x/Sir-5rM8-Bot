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
