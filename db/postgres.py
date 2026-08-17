"""Neon / Postgres storage backend (psycopg)."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

import config
from db._base import get_database_url

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
except ImportError as exc:  # pragma: no cover
    raise RuntimeError(
        "psycopg is required for DATABASE_URL / Neon. pip install 'psycopg[binary]'"
    ) from exc


@contextmanager
def _conn() -> Iterator[psycopg.Connection]:
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    with psycopg.connect(url, row_factory=dict_row) as conn:
        yield conn
        conn.commit()


def check_connection() -> None:
    with _conn() as conn:
        conn.execute("SELECT 1 FROM rate_state WHERE id = 1 LIMIT 1")


def _ensure_karma_settings_row(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        INSERT INTO karma_global_settings (id, cooldown_hours, history_limit)
        VALUES (1, %s, %s)
        ON CONFLICT (id) DO NOTHING
        """,
        (config.DEFAULT_COOLDOWN_HOURS, config.DEFAULT_KARMA_HISTORY_LIMIT),
    )


def _ensure_rate_state_row(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        INSERT INTO rate_state (id, previous_rates)
        VALUES (1, NULL)
        ON CONFLICT (id) DO NOTHING
        """
    )


def set_rate_notification(guild_id: str, channel_id: str, role_id: str) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO guild_rate_notifications (guild_id, channel_id, role_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (guild_id) DO UPDATE
              SET channel_id = EXCLUDED.channel_id,
                  role_id = EXCLUDED.role_id
            """,
            (guild_id, channel_id, role_id),
        )


def get_rate_notification(guild_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT channel_id, role_id
            FROM guild_rate_notifications
            WHERE guild_id = %s
            LIMIT 1
            """,
            (guild_id,),
        ).fetchone()
    if not row:
        return None
    return {"channel_id": row["channel_id"], "role_id": row["role_id"]}


def clear_rate_notification(guild_id: str) -> bool:
    if get_rate_notification(guild_id) is None:
        return False
    with _conn() as conn:
        conn.execute(
            "DELETE FROM guild_rate_notifications WHERE guild_id = %s",
            (guild_id,),
        )
    return True


def get_rate_notification_channels() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT guild_id, channel_id, role_id FROM guild_rate_notifications"
        ).fetchall()
    return [
        {
            "server_id": row["guild_id"],
            "channel_id": row["channel_id"],
            "role": row["role_id"],
        }
        for row in rows
    ]


def get_previous_rate_values() -> dict | None:
    with _conn() as conn:
        _ensure_rate_state_row(conn)
        row = conn.execute(
            "SELECT previous_rates FROM rate_state WHERE id = 1 LIMIT 1"
        ).fetchone()
    if not row or row.get("previous_rates") is None:
        return None
    return row["previous_rates"]


def save_previous_rate_values(values: dict) -> None:
    with _conn() as conn:
        _ensure_rate_state_row(conn)
        conn.execute(
            "UPDATE rate_state SET previous_rates = %s WHERE id = 1",
            (Jsonb(values),),
        )


def get_karma_settings() -> dict:
    with _conn() as conn:
        _ensure_karma_settings_row(conn)
        row = conn.execute(
            """
            SELECT cooldown_hours, history_limit
            FROM karma_global_settings
            WHERE id = 1
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return {
            "cooldown_hours": config.DEFAULT_COOLDOWN_HOURS,
            "history_limit": config.DEFAULT_KARMA_HISTORY_LIMIT,
        }
    return {
        "cooldown_hours": row.get("cooldown_hours") or config.DEFAULT_COOLDOWN_HOURS,
        "history_limit": row.get("history_limit") or config.DEFAULT_KARMA_HISTORY_LIMIT,
    }


def karma_get_balance(user_id: str) -> int:
    with _conn() as conn:
        row = conn.execute(
            "SELECT balance FROM karma_balances WHERE user_id = %s LIMIT 1",
            (user_id,),
        ).fetchone()
    if not row:
        return 0
    return int(row.get("balance") or 0)


def karma_get_cooldown(giver_id: str, receiver_id: str) -> datetime | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT last_given
            FROM karma_cooldowns
            WHERE giver_id = %s AND receiver_id = %s
            LIMIT 1
            """,
            (giver_id, receiver_id),
        ).fetchone()
    if not row or not row.get("last_given"):
        return None
    dt = row["last_given"]
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def karma_add(giver_id: str, receiver_id: str, giver_name: str, reason: str) -> int:
    now = datetime.now(timezone.utc)
    with _conn() as conn:
        row = conn.execute(
            "SELECT karma_increment_balance(%s) AS balance",
            (receiver_id,),
        ).fetchone()
        if not row or row.get("balance") is None:
            raise RuntimeError(
                "karma_increment_balance failed — apply neon/schema.sql (or supabase/schema.sql)"
            )
        new_bal = int(row["balance"])
        conn.execute(
            """
            INSERT INTO karma_cooldowns (giver_id, receiver_id, last_given)
            VALUES (%s, %s, %s)
            ON CONFLICT (giver_id, receiver_id) DO UPDATE
              SET last_given = EXCLUDED.last_given
            """,
            (giver_id, receiver_id, now),
        )
        conn.execute(
            """
            INSERT INTO karma_events
              (user_id, created_at, action, amount, by_name, giver_id, admin_id, reason)
            VALUES (%s, %s, 'add', 1, %s, %s, NULL, %s)
            """,
            (receiver_id, now, giver_name, giver_id, reason),
        )
    return new_bal


def karma_take(target_id: str, admin_id: str, admin_name: str) -> int | None:
    now = datetime.now(timezone.utc)
    with _conn() as conn:
        row = conn.execute(
            "SELECT karma_decrement_balance(%s) AS balance",
            (target_id,),
        ).fetchone()
        if not row or row.get("balance") is None:
            return None
        new_bal = int(row["balance"])
        conn.execute(
            """
            INSERT INTO karma_events
              (user_id, created_at, action, amount, by_name, giver_id, admin_id, reason)
            VALUES (%s, %s, 'remove', 1, %s, NULL, %s, NULL)
            """,
            (target_id, now, admin_name, admin_id),
        )
    return new_bal


def _event_row_to_history_dict(row: dict[str, Any]) -> dict:
    ts = row.get("created_at")
    if hasattr(ts, "isoformat"):
        ts = ts.isoformat()
    return {
        "timestamp": ts,
        "action": row["action"],
        "amount": row.get("amount", 1),
        "by": row.get("by_name") or "?",
        "giver_id": row.get("giver_id"),
        "admin_id": row.get("admin_id"),
        "reason": row.get("reason"),
    }


def karma_get_history(user_id: str) -> list[dict]:
    limit = get_karma_settings()["history_limit"]
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT created_at, action, amount, by_name, giver_id, admin_id, reason
            FROM karma_events
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [_event_row_to_history_dict(row) for row in rows]


def karma_get_audit(limit: int = 20) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT user_id, created_at, action, amount, by_name, giver_id, admin_id, reason
            FROM karma_events
            WHERE action = 'remove'
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
    out = []
    for row in rows:
        ts = row.get("created_at")
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        out.append({
            "user_id": row["user_id"],
            "timestamp": ts,
            "action": row["action"],
            "amount": row.get("amount", 1),
            "by": row.get("by_name") or "?",
            "admin_id": row.get("admin_id"),
        })
    return out


def apply_schema(schema_sql: str) -> None:
    """Run DDL from schema.sql against DATABASE_URL (multi-statement)."""
    url = get_database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    # Simple query protocol accepts multiple statements in one script.
    with psycopg.connect(url, autocommit=True) as conn:
        conn.pgconn.exec_(schema_sql.encode("utf-8"))


def database_counts() -> dict[str, int]:
    with _conn() as conn:
        counts: dict[str, int] = {}
        for table in (
            "guild_rate_notifications",
            "karma_balances",
            "karma_cooldowns",
            "karma_events",
        ):
            row = conn.execute(f"SELECT COUNT(*)::int AS n FROM {table}").fetchone()
            counts[table] = int(row["n"] if row else 0)
        row = conn.execute(
            "SELECT previous_rates IS NOT NULL AS has_data FROM rate_state WHERE id = 1"
        ).fetchone()
        counts["rate_state_has_data"] = int(bool(row and row["has_data"]))
    return counts


def import_payload(payload: dict[str, Any], *, force: bool = False) -> None:
    """Upsert a migration payload (same shape as db.migrate_json collect)."""
    counts = database_counts()
    has_data = (
        counts["guild_rate_notifications"]
        or counts["karma_balances"]
        or counts["karma_cooldowns"]
        or counts["karma_events"]
        or counts["rate_state_has_data"]
    )
    if has_data and not force:
        raise RuntimeError(
            "Neon already has data. Re-run with --force to overwrite/upsert."
        )

    with _conn() as conn:
        for row in payload.get("guild_notifications", []):
            conn.execute(
                """
                INSERT INTO guild_rate_notifications (guild_id, channel_id, role_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (guild_id) DO UPDATE
                  SET channel_id = EXCLUDED.channel_id,
                      role_id = EXCLUDED.role_id
                """,
                (row["guild_id"], row["channel_id"], row["role_id"]),
            )
        for row in payload.get("balances", []):
            conn.execute(
                """
                INSERT INTO karma_balances (user_id, balance)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET balance = EXCLUDED.balance
                """,
                (row["user_id"], int(row["balance"])),
            )
        for row in payload.get("cooldowns", []):
            conn.execute(
                """
                INSERT INTO karma_cooldowns (giver_id, receiver_id, last_given)
                VALUES (%s, %s, %s)
                ON CONFLICT (giver_id, receiver_id) DO UPDATE
                  SET last_given = EXCLUDED.last_given
                """,
                (row["giver_id"], row["receiver_id"], row["last_given"]),
            )
        settings = payload.get("settings") or {}
        conn.execute(
            """
            INSERT INTO karma_global_settings (id, cooldown_hours, history_limit)
            VALUES (1, %s, %s)
            ON CONFLICT (id) DO UPDATE
              SET cooldown_hours = EXCLUDED.cooldown_hours,
                  history_limit = EXCLUDED.history_limit
            """,
            (
                int(settings.get("cooldown_hours", config.DEFAULT_COOLDOWN_HOURS)),
                int(settings.get("history_limit", config.DEFAULT_KARMA_HISTORY_LIMIT)),
            ),
        )
        if payload.get("rate_state") is not None:
            conn.execute(
                """
                INSERT INTO rate_state (id, previous_rates)
                VALUES (1, %s)
                ON CONFLICT (id) DO UPDATE SET previous_rates = EXCLUDED.previous_rates
                """,
                (Jsonb(payload["rate_state"]),),
            )
        for row in payload.get("events", []):
            conn.execute(
                """
                INSERT INTO karma_events
                  (user_id, created_at, action, amount, by_name, giver_id, admin_id, reason)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row["user_id"],
                    row["created_at"],
                    row["action"],
                    int(row.get("amount", 1)),
                    row.get("by_name"),
                    row.get("giver_id"),
                    row.get("admin_id"),
                    row.get("reason"),
                ),
            )


# --- Bothunter ---

def _bothunter_row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    experiments = row.get("experiments") or []
    if isinstance(experiments, str):
        import json
        try:
            experiments = json.loads(experiments)
        except (json.JSONDecodeError, TypeError):
            experiments = []
    return {
        "guild_id": str(row["guild_id"]),
        "channel_id": str(row["channel_id"]) if row.get("channel_id") else None,
        "log_channel_id": str(row["log_channel_id"]) if row.get("log_channel_id") else None,
        "action": row.get("action") or "softban",
        "warning_msg_id": str(row["warning_msg_id"]) if row.get("warning_msg_id") else None,
        "experiments": list(experiments),
        "warning_message": row.get("warning_message"),
        "dm_message": row.get("dm_message"),
        "log_message": row.get("log_message"),
        "reinvite_code": row.get("reinvite_code"),
    }


def get_bothunter_config(guild_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT guild_id, channel_id, log_channel_id, action, warning_msg_id,
                   experiments, warning_message, dm_message, log_message, reinvite_code
            FROM bothunter_config
            WHERE guild_id = %s
            """,
            (str(guild_id),),
        ).fetchone()
    return _bothunter_row_to_dict(row)


def set_bothunter_config(config: dict) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO bothunter_config (
              guild_id, channel_id, log_channel_id, action, warning_msg_id,
              experiments, warning_message, dm_message, log_message, reinvite_code
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (guild_id) DO UPDATE SET
              channel_id = EXCLUDED.channel_id,
              log_channel_id = EXCLUDED.log_channel_id,
              action = EXCLUDED.action,
              warning_msg_id = EXCLUDED.warning_msg_id,
              experiments = EXCLUDED.experiments,
              warning_message = EXCLUDED.warning_message,
              dm_message = EXCLUDED.dm_message,
              log_message = EXCLUDED.log_message,
              reinvite_code = EXCLUDED.reinvite_code
            """,
            (
                str(config["guild_id"]),
                config.get("channel_id"),
                config.get("log_channel_id"),
                config.get("action") or "softban",
                config.get("warning_msg_id"),
                Jsonb(list(config.get("experiments") or [])),
                config.get("warning_message"),
                config.get("dm_message"),
                config.get("log_message"),
                config.get("reinvite_code"),
            ),
        )


def clear_bothunter_config(guild_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM bothunter_config WHERE guild_id = %s",
            (str(guild_id),),
        )
        return cur.rowcount > 0


def log_bothunter_event(guild_id: str, user_id: str, channel_id: str | None = None) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO bothunter_events (guild_id, user_id, channel_id)
            VALUES (%s, %s, %s)
            """,
            (str(guild_id), str(user_id), str(channel_id) if channel_id else None),
        )


def get_bothunter_moderated_count(guild_id: str, channel_id: str | None = None) -> int:
    with _conn() as conn:
        if channel_id:
            row = conn.execute(
                """
                SELECT COUNT(*)::int AS n FROM bothunter_events
                WHERE guild_id = %s AND channel_id = %s
                """,
                (str(guild_id), str(channel_id)),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*)::int AS n FROM bothunter_events WHERE guild_id = %s",
                (str(guild_id),),
            ).fetchone()
    return int(row["n"] if row else 0)


def get_bothunter_channel_map() -> dict[str, str]:
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT guild_id, channel_id FROM bothunter_config
            WHERE channel_id IS NOT NULL
            """
        ).fetchall()
    return {str(r["channel_id"]): str(r["guild_id"]) for r in rows}


# --- Server player sampling ---

def watch_server(server_key: str, session_name: str | None = None) -> None:
    """Upsert a watched server and bump last_queried. Evicts oldest if over max."""
    key = str(server_key).strip()
    if not key:
        return
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO server_watchlist (server_key, session_name, last_queried)
            VALUES (%s, %s, NOW())
            ON CONFLICT (server_key) DO UPDATE SET
              session_name = COALESCE(EXCLUDED.session_name, server_watchlist.session_name),
              last_queried = NOW()
            """,
            (key, session_name),
        )
        count = conn.execute(
            "SELECT COUNT(*)::int AS n FROM server_watchlist"
        ).fetchone()["n"]
        overflow = int(count) - config.SERVER_WATCHLIST_MAX
        if overflow > 0:
            conn.execute(
                """
                DELETE FROM server_watchlist
                WHERE server_key IN (
                  SELECT server_key FROM server_watchlist
                  ORDER BY last_queried ASC
                  LIMIT %s
                )
                """,
                (overflow,),
            )


def record_server_sample(
    server_key: str,
    num_players: int,
    max_players: int,
    *,
    sampled_at: datetime | None = None,
) -> None:
    key = str(server_key).strip()
    if not key:
        return
    ts = sampled_at or datetime.now(timezone.utc)
    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO server_watchlist (server_key, last_queried)
            VALUES (%s, %s)
            ON CONFLICT (server_key) DO NOTHING
            """,
            (key, ts),
        )
        conn.execute(
            """
            INSERT INTO server_player_samples
              (server_key, num_players, max_players, sampled_at)
            VALUES (%s, %s, %s, %s)
            """,
            (key, int(num_players), int(max_players), ts),
        )


def get_server_player_history(
    server_key: str,
    *,
    hours: int | None = None,
) -> list[dict]:
    key = str(server_key).strip()
    if not key:
        return []
    window = hours if hours is not None else config.SERVER_HISTORY_HOURS
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT num_players, max_players, sampled_at
            FROM server_player_samples
            WHERE server_key = %s
              AND sampled_at >= NOW() - (%s || ' hours')::interval
            ORDER BY sampled_at ASC
            """,
            (key, str(int(window))),
        ).fetchall()
    out: list[dict] = []
    for row in rows:
        ts = row["sampled_at"]
        if hasattr(ts, "isoformat"):
            ts = ts.isoformat()
        out.append({
            "num_players": int(row["num_players"]),
            "max_players": int(row["max_players"]),
            "sampled_at": ts,
        })
    return out


def list_watched_server_keys() -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT server_key FROM server_watchlist ORDER BY last_queried DESC"
        ).fetchall()
    return [str(r["server_key"]) for r in rows]


def prune_server_samples(*, retention_days: int | None = None) -> int:
    days = retention_days if retention_days is not None else config.SERVER_SAMPLE_RETENTION_DAYS
    with _conn() as conn:
        cur = conn.execute(
            """
            DELETE FROM server_player_samples
            WHERE sampled_at < NOW() - (%s || ' days')::interval
            """,
            (str(int(days)),),
        )
        return int(cur.rowcount or 0)


def add_up_notify(
    server_key: str,
    user_id: str,
    channel_id: str,
    guild_id: str | None = None,
    query: str | None = None,
    session_name: str | None = None,
) -> bool:
    key = str(server_key).strip()
    uid = str(user_id).strip()
    cid = str(channel_id).strip()
    if not key or not uid or not cid:
        return False
    with _conn() as conn:
        row = conn.execute(
            """
            INSERT INTO server_up_notify
              (server_key, user_id, channel_id, guild_id, query, session_name)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (server_key, user_id, channel_id) DO NOTHING
            RETURNING user_id
            """,
            (key, uid, cid, guild_id, query, session_name),
        ).fetchone()
    return row is not None


def list_up_notify_keys() -> list[str]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT server_key FROM server_up_notify ORDER BY server_key"
        ).fetchall()
    return [str(r["server_key"]) for r in rows]


def list_up_notify_watchers(server_key: str) -> list[dict]:
    key = str(server_key).strip()
    if not key:
        return []
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT server_key, user_id, channel_id, guild_id, query, session_name
            FROM server_up_notify
            WHERE server_key = %s
            """,
            (key,),
        ).fetchall()
    return [dict(r) for r in rows]


def clear_up_notify(server_key: str, channel_id: str | None = None) -> int:
    key = str(server_key).strip()
    if not key:
        return 0
    with _conn() as conn:
        if channel_id:
            cur = conn.execute(
                """
                DELETE FROM server_up_notify
                WHERE server_key = %s AND channel_id = %s
                """,
                (key, str(channel_id)),
            )
        else:
            cur = conn.execute(
                "DELETE FROM server_up_notify WHERE server_key = %s",
                (key,),
            )
        return int(cur.rowcount or 0)
