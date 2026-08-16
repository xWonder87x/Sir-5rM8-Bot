# Sir-5rM8 — agent notes

Follow **`BOT_BLUEPRINT.md`** for architecture and validation. This file is bot-specific.

## Purpose

Discord bot for ARK: Survival Ascended communities: live official PVE rates, server status lookup, karma system, per-guild rate-change notifications, and bothunter (spam-trap channel).

## Extension load order

Defined in `commands/core/extensions.py` (`COG_EXTENSIONS`):

1. `commands.core.help`
2. `commands.core.sync_commands`
3. `commands.core.admin`
4. `commands.community.rates`
5. `commands.community.server`
6. `commands.community.karma`
7. `commands.mod.bothunter`
8. `commands.integrations.ratecheck`
9. `commands.integrations.serversample`

## Slash commands

| Command | Cog | Notes |
|---------|-----|-------|
| `/help` | `commands.core.help` | Setup guide |
| `/sync-commands` | `commands.core.sync_commands` | Admin only |
| `/say`, `/set_rate_channel`, `/rate_channel_status`, `/clear_rate_channel`, `/servers` | `commands.core.admin` | Admin tools |
| `/rates` | `commands.community.rates` | Live ASA rates |
| `/serverstatus` | `commands.community.server` | Server lookup |
| `/karma`, `/manage_karma` | `commands.community.karma` | Karma system |
| `/bothunter`, `/bothunter-messages` | `commands.mod.bothunter` | Spam-trap channel (honeypot port) |

No user-facing prefix commands.

## Environment variables

### Required

| Variable | Purpose |
|----------|---------|
| `TOKEN` | Discord bot token |

### Supabase / Neon (optional — JSON fallback when unset)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` or `NEON_DATABASE_URL` | Neon/Postgres connection string (**preferred** when set) |
| `SUPABASE_URL` | Discord Bots project URL (used only if no `DATABASE_URL`) |
| `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY` | Per-bot JWT (`role=bot_sir5rm8`) or admin key |
| `SUPABASE_BOT_JWT` + `SUPABASE_PUBLISHABLE_KEY` | Alternative JWT auth pair |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_DIR` | `data/` | Runtime JSON + bot.log |
| `SLASH_SYNC_GUILD_IDS` | — | Comma-separated guild IDs for stale slash clears |
| `RESTART_NOTIFY_USER_ID` | `464386520124620800` | Discord user ID to DM once per process startup; empty disables |
| `SERVER_SAMPLE_INTERVAL_MINUTES` | `5` | How often to sample watched ASA servers for player graphs |
| `SERVER_HISTORY_HOURS` | `24` | Window shown on `/serverstatus` history chart |
| `SERVER_SAMPLE_RETENTION_DAYS` | `7` | Prune older player samples |
| `LOGIN_RETRY_ATTEMPT` | — | Internal; set on 429 restart |

## Database

**Preferred:** Neon/Postgres via `DATABASE_URL` — see **`neon/README.md`**.

**Legacy:** Shared **Discord Bots** Supabase project (`msksvvopixdaqhvdewvw`), role **`bot_sir5rm8`**.

| Table | Purpose |
|-------|---------|
| `guild_rate_notifications` | Per-guild rate alert channel + role |
| `rate_state` | Previous ASA rates for change detection |
| `karma_*` | Karma balances, cooldowns, events, settings |
| `bothunter_config` | Per-guild trap channel, action, experiments, messages |
| `bothunter_events` | Bothunter moderation event log |
| `server_watchlist` | ASA servers sampled for `/serverstatus` graphs |
| `server_player_samples` | Player-count time series for history charts |

Without a remote DB, the same data lives under `data/` as JSON.

See **`neon/README.md`**, **`supabase/README.md`**, and **`../ALICE/docs/UNIFIED_SUPABASE.md`**.

## Reliability notes

- Prefer `DATABASE_URL` (Neon/Postgres) when set; else Supabase; else JSON files under `data/`.
- Offload sync Supabase/JSON/Postgres storage from async slash handlers with `asyncio.to_thread(...)`.
- Prefer `interaction.response.defer(...)` before any storage or network work, then `followup`.
- Extension load failure aborts startup (`bot.close()`); do not mark the bot ready with a half-loaded tree.
- Slash sync: guild-scope clears are best-effort; global sync success is what matters. Retry global sync on later `on_ready` if the first attempt failed.
- Universal rules live in **`BOT_BLUEPRINT.md`** — keep this file bot-specific.

## Validation

```bash
python -m compileall main.py commands db config.py functions
python -m pyflakes main.py config.py db functions commands 2>/dev/null || true
python scripts/verify_extensions.py
python -c "import db; print(db.check_schema())"   # when Supabase configured
pytest -q
```
