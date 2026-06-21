# Sir-5rM8 — agent notes

Follow **`BOT_BLUEPRINT.md`** for architecture and validation. This file is bot-specific.

## Purpose

Discord bot for ARK: Survival Ascended communities: live official PVE rates, server status lookup, karma system, and per-guild rate-change notifications.

## Extension load order

Defined in `commands/core/extensions.py` (`COG_EXTENSIONS`):

1. `commands.core.help`
2. `commands.core.sync_commands`
3. `commands.core.admin`
4. `commands.community.rates`
5. `commands.community.server`
6. `commands.community.karma`
7. `commands.integrations.ratecheck`

## Slash commands

| Command | Cog | Notes |
|---------|-----|-------|
| `/help` | `commands.core.help` | Setup guide |
| `/sync-commands` | `commands.core.sync_commands` | Admin only |
| `/say`, `/set_rate_channel`, `/rate_channel_status`, `/clear_rate_channel`, `/servers` | `commands.core.admin` | Admin tools |
| `/rates` | `commands.community.rates` | Live ASA rates |
| `/serverstatus` | `commands.community.server` | Server lookup |
| `/karma`, `/manage_karma` | `commands.community.karma` | Karma system |

No user-facing prefix commands.

## Environment variables

### Required

| Variable | Purpose |
|----------|---------|
| `TOKEN` | Discord bot token |

### Supabase (optional — JSON fallback when unset)

| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Discord Bots project URL |
| `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY` | Per-bot JWT (`role=bot_sir5rm8`) or admin key |
| `SUPABASE_BOT_JWT` + `SUPABASE_PUBLISHABLE_KEY` | Alternative JWT auth pair |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_DIR` | `data/` | Runtime JSON + bot.log |
| `SLASH_SYNC_GUILD_IDS` | — | Comma-separated guild IDs for stale slash clears |
| `LOGIN_RETRY_ATTEMPT` | — | Internal; set on 429 restart |

## Database

Shared **Discord Bots** Supabase project (`msksvvopixdaqhvdewvw`). Postgres role **`bot_sir5rm8`**.

| Table | Purpose |
|-------|---------|
| `guild_rate_notifications` | Per-guild rate alert channel + role |
| `rate_state` | Previous ASA rates for change detection |
| `karma_*` | Karma balances, cooldowns, events, settings |

Without Supabase, the same data lives under `data/` as JSON.

See **`supabase/README.md`** and **`../ALICE/docs/UNIFIED_SUPABASE.md`**.

## Validation

```bash
python -m compileall main.py commands db config.py functions
python -m pyflakes main.py config.py db functions commands 2>/dev/null || true
python scripts/verify_extensions.py
python -c "import db; print(db.check_schema())"   # when Supabase configured
pytest -q
```
