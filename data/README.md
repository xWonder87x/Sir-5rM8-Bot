# Data Directory

This directory stores bot state and guild configurations. It is created automatically when the bot runs.

## Structure

```
data/
├── config.json           # Guild settings (rate notifications, etc.)
└── rate_state/
    └── previous_values.json  # Previous parsed rate values for change detection
```

## config.json

Stored per-guild:

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
  }
}
```

`config.json` and `rate_state/` are gitignored to avoid committing user data.
