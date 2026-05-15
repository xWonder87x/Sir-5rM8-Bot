"""
Storage backend: Supabase when SUPABASE_URL + SUPABASE_SERVICE_KEY are set,
otherwise JSON files under data/ (see storage_files.py).
"""
from utils import config

if config.USE_SUPABASE:
    from utils.storage_supabase import (  # noqa: F401
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
    from utils.storage_files import (  # noqa: F401
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
