# Sir-5rM8 — agent notes

Follow **`BOT_BLUEPRINT.md`** for architecture and validation. This file is bot-specific.

## Purpose

Discord bot for ARK: Survival Ascended communities: live official PVE rates, server status lookup, official in-game notice relay, karma system, per-guild rate-change notifications, and bothunter (spam-trap channel).

## Extension load order

Defined in `commands/core/extensions.py` (`COG_EXTENSIONS`):

1. `commands.core.help`
2. `commands.core.sync_commands`
3. `commands.core.admin`
4. `commands.core.guild_list`
5. `commands.community.rates`
6. `commands.community.server`
7. `commands.community.ark_notifications`
8. `commands.community.karma`
9. `commands.mod.bothunter`
10. `commands.integrations.ratecheck`

## Slash commands

| Command | Cog | Notes |
|---------|-----|-------|
| `/help` | `commands.core.help` | Setup guide |
| `/sync-commands` | `commands.core.sync_commands` | Admin only |
| `/say`, `/set_rate_channel`, `/rate_channel_status`, `/clear_rate_channel` | `commands.core.admin` | Admin tools |
| `/rates` | `commands.community.rates` | Live ASA rates; Subscribe / Unsubscribe rate-alert role |
| `/serverstatus` | `commands.community.server` | Official-list status + occupancy; BM uptime graph fallback |
| `/arknotifications` | `commands.community.ark_notifications` | Admin channel picker for official in-game ASA notices |
| `/karma`, `/manage_karma` | `commands.community.karma` | Karma system |
| `/bothunter`, `/bothunter-messages` | `commands.mod.bothunter` | Spam-trap channel (honeypot port) |

No user-facing prefix commands.

## Environment variables

### Required

| Variable | Purpose |
|----------|---------|
| `TOKEN` | Discord bot token |

### Postgres (optional — JSON fallback when unset)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Postgres connection string (**preferred** when set) |
| `POSTGREST_URL` | Postgres REST project URL (used only if no `DATABASE_URL`) |
| `POSTGREST_KEY` | Per-bot JWT (`role=bot_sir5rm8`) or admin key |
| `POSTGREST_JWT` + `POSTGREST_ANON_KEY` | Alternative JWT auth pair |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATA_DIR` | `data/` | Runtime JSON + bot.log |
| `SLASH_SYNC_GUILD_IDS` | — | Comma-separated guild IDs for stale slash clears |
| `GUILD_LIST_CHANNEL_ID` | `1540099281896087583` | Text channel for the sticky list of Discord guilds the bot is in (replaces `/servers`) |
| `RESTART_NOTIFY_USER_ID` | `464386520124620800` | Discord user to DM on restart and ping in `GUILD_LIST_CHANNEL_ID` when the bot joins a guild; empty disables |
| `BATTLEMETRICS_TOKEN` | — | Optional. Uptime graph + BM fallback/validation for `/serverstatus` |
| `BM_UPTIME_HISTORY_DAYS` | `90` | Downtime→uptime history window on the chart |
| `BM_UPTIME_RESOLUTION_MINUTES` | `60` | BattleMetrics downtime bucket size (`60` or `1440`) |
| `SERVER_UP_CHECK_MINUTES` | `1` | How often to poll watched offline servers for notify-when-up |
| `OUTAGE_REPORT_URL` | Google Form | Offline **Report Outage** link; prefilled from the `/serverstatus` lookup |
| `ASA_POLL_SECONDS` | `60` | Official list / network-status poll interval |
| `ASA_CACHE_TTL_SECONDS` | `60` | Serve cached official list newer than this |
| `ASA_OFFLINE_MISS_THRESHOLD` | `2` | Consecutive successful-list misses before OFFLINE |
| `ASA_STALE_SECONDS` | `300` | Treat LastUpdated older than this as UNKNOWN |
| `ASA_BM_FALLBACK` | `1` | Use BattleMetrics for uptime graph and missing-server identity |
| `ASA_BM_COMPARE` | `1` | Log official vs BattleMetrics online/offline disagreements |
| `LOGIN_RETRY_ATTEMPT` | — | Internal; set on 429 restart |

## Database

**Preferred:** Postgres via `DATABASE_URL` — see **`postgres/README.md`**.

**Legacy REST:** Shared **Discord Bots** project (`msksvvopixdaqhvdewvw`), role **`bot_sir5rm8`**.

| Table | Purpose |
|-------|---------|
| `guild_rate_notifications` | Per-guild rate alert channel + role |
| `rate_state` | Previous ASA rates for change detection |
| `guild_ark_notifications` | Per-guild channel for official in-game ASA notices |
| `ark_notification_state` | Previous `notification.html` text for change detection |
| `karma_*` | Karma balances, cooldowns, events, settings |
| `bothunter_config` | Per-guild trap channel, action, experiments, messages |
| `bothunter_events` | Bothunter moderation event log |
| `server_watchlist` | Legacy local sample watchlist (unused by live chart) |
| `server_player_samples` | Legacy local player samples (unused by live chart) |
| `server_up_notify` | Users waiting for an offline server to come back |

Without a remote DB, the same data lives under `data/` as JSON.

See **`postgres/README.md`**, **`docs/DATABASE.md`**, and **`../ALICE/docs/UNIFIED_SUPABASE.md`**.

## Official ASA monitoring

Primary CDN endpoints (see `functions/asa_client.py` + `functions/asa_cache.py`):

- `https://cdn2.arkdedicated.com/servers/asa/officialserverlist.json`
- `https://cdn2.arkdedicated.com/asa/officialserverstatus.ini` (global network, not per-server)
- `https://cdn2.arkdedicated.com/asa/notification.html`

Matching order: SessionID, exact `Name`, IP / IP:port, numeric server id in the session name, then exact session name. Substring match is last resort.

`/arknotifications` relays `notification.html` to a guild-chosen Discord channel when the text changes to a non-empty notice. Empty pages (`..`) are stored but not posted. The first observation after a restart is seeded without posting.

Per-server ONLINE means the row is in the latest **successful** list and `LastUpdated` is fresher than `ASA_STALE_SECONDS`. Missing rows increment a miss counter; after `ASA_OFFLINE_MISS_THRESHOLD` they become OFFLINE. A CDN failure is `API_UNAVAILABLE` and keeps last-known state. `ServerPing` is latency, not an online flag — Wildcard does not publish an authoritative per-server heartbeat.

BattleMetrics remains optional for the uptime chart (official list has no history) and for identity when a known numeric server is missing. Disable with `ASA_BM_FALLBACK=0`.

## Reliability notes

- Prefer `DATABASE_URL` (Postgres) when set; else Postgres REST; else JSON files under `data/`.
- Offload sync Postgres/JSON storage from async slash handlers with `asyncio.to_thread(...)`.
- Prefer `interaction.response.defer(...)` before any storage or network work, then `followup`.
- Extension load failure aborts startup (`bot.close()`); do not mark the bot ready with a half-loaded tree.
- Slash sync: guild-scope clears are best-effort; global sync success is what matters. Retry global sync on later `on_ready` if the first attempt failed.
- Universal rules live in **`BOT_BLUEPRINT.md`** — keep this file bot-specific.

## Validation

```bash
python -m compileall main.py commands db config.py functions
python -m pyflakes main.py config.py db functions commands 2>/dev/null || true
python scripts/verify_extensions.py
python -c "import db; print(db.check_schema())" # when a remote database is configured
pytest -q
```
