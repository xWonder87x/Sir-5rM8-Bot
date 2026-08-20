# Data Directory

When **no remote database** is configured (`DATABASE_URL` or Postgres REST vars in `.env`), the bot stores state here. See [postgres/README.md](../postgres/README.md).

This directory is created automatically when the bot runs with file storage.

## Structure

```
data/
├── config.json             # Guild settings (rate + ARK notice channels)
├── guild_list_message.json # Sticky message id for the guild-list embed
└── rate_state/
    ├── previous_values.json  # Previous parsed rate values for change detection
    └── ark_notice.json       # Previous official in-game notice text
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
      },
      "ark_notifications": {
        "channel_id": "..."
      }
    }
  }
}
```

- **guilds** — Per-server rate notification and official in-game notice settings

`config.json`, `guild_list_message.json`, and `rate_state/` are gitignored to avoid committing user data.
