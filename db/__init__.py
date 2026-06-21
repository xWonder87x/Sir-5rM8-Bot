"""Database package — all persistence goes through here."""
from __future__ import annotations

from db._base import EXPECTED_SCHEMA, check_schema, use_supabase

if use_supabase():
    from db.supabase import (  # noqa: F401
        check_connection,
        clear_rate_notification,
        get_karma_settings,
        get_previous_rate_values,
        get_rate_notification,
        get_rate_notification_channels,
        karma_add,
        karma_get_audit,
        karma_get_balance,
        karma_get_cooldown,
        karma_get_history,
        karma_take,
        save_previous_rate_values,
        set_rate_notification,
    )
else:
    from db.files import (  # noqa: F401
        clear_rate_notification,
        get_karma_settings,
        get_previous_rate_values,
        get_rate_notification,
        get_rate_notification_channels,
        karma_add,
        karma_get_audit,
        karma_get_balance,
        karma_get_cooldown,
        karma_get_history,
        karma_take,
        save_previous_rate_values,
        set_rate_notification,
    )

    def check_connection() -> None:
        """JSON file backend — no remote connection to verify."""
        return None
