"""Database package — all persistence goes through here."""
from __future__ import annotations

from db._base import (  # noqa: F401
    EXPECTED_SCHEMA,
    check_schema,
    storage_backend_name,
    use_postgres,
    use_supabase,
)

_BOTHUNTER_EXPORTS = (
    "clear_bothunter_config",
    "get_bothunter_channel_map",
    "get_bothunter_config",
    "get_bothunter_moderated_count",
    "log_bothunter_event",
    "set_bothunter_config",
)

if use_postgres():
    from db.postgres import (  # noqa: F401
        check_connection,
        clear_bothunter_config,
        clear_rate_notification,
        get_bothunter_channel_map,
        get_bothunter_config,
        get_bothunter_moderated_count,
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
        log_bothunter_event,
        save_previous_rate_values,
        set_bothunter_config,
        set_rate_notification,
    )
elif use_supabase():
    from db.supabase import (  # noqa: F401
        check_connection,
        clear_bothunter_config,
        clear_rate_notification,
        get_bothunter_channel_map,
        get_bothunter_config,
        get_bothunter_moderated_count,
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
        log_bothunter_event,
        save_previous_rate_values,
        set_bothunter_config,
        set_rate_notification,
    )
else:
    from db.files import (  # noqa: F401
        clear_bothunter_config,
        clear_rate_notification,
        get_bothunter_channel_map,
        get_bothunter_config,
        get_bothunter_moderated_count,
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
        log_bothunter_event,
        save_previous_rate_values,
        set_bothunter_config,
        set_rate_notification,
    )

    def check_connection() -> None:
        """JSON file backend — no remote connection to verify."""
        return None
