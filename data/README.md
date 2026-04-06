# Data Directory

When **Supabase** is not configured (`SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `.env`), the bot stores state here. See [docs/SUPABASE.md](../docs/SUPABASE.md) to use PostgreSQL instead.

This directory is created automatically when the bot runs with file storage.

## Structure

```
data/
├── config.json             # Guild settings + karma balances & cooldowns
├── karma_history.jsonl     # Append-only karma event log (one JSON object per line)
└── rate_state/
    └── previous_values.json  # Previous parsed rate values for change detection
```

## config.json

```json
{
  "version": 1,
  "guilds": {
    "guild_id": {
      "rate_notifications": {
        "channel_id": "...",
        "role_id": "..."
      }
    }
  },
  "karma": {
    "balances": { "user_id": 5 },
    "cooldowns": { "giver_id:receiver_id": "2025-02-11T12:00:00" },
    "cooldown_hours": 24,
    "history_limit": 10
  }
}
```

- **guilds** — Per-server rate notification settings
- **karma.balances** — Global karma per user (shared across all servers)
- **karma.cooldowns** — Last karma-given timestamp per (giver, receiver) pair
- **karma.cooldown_hours** — Hours before giving karma to the same person again (default: 24)
- **karma.history_limit** — Max history entries per user (default: 10)

## karma_history.jsonl

Append-only log of karma events. Each line is a JSON object:

```json
{"user_id": "123", "timestamp": "2025-02-11T14:30:00", "action": "add", "amount": 1, "by": "Alice", "giver_id": "456", "reason": "for helping"}
{"user_id": "123", "timestamp": "2025-02-11T12:00:00", "action": "remove", "amount": 1, "by": "ModAdmin", "admin_id": "789"}
```

- **user_id** — Target user whose karma changed
- **action** — `"add"` or `"remove"`
- **amount** — Karma amount (typically 1)
- **by** — Username of giver (add) or admin (remove)
- **giver_id** — Discord user ID of giver (add; for pingable mentions)
- **admin_id** — Discord user ID of admin (remove; for pingable mentions)
- **reason** — Reason when giving (add only; required)

`config.json`, `karma_history.jsonl`, and `rate_state/` are gitignored to avoid committing user data.
