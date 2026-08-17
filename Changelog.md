# Changelog

## [1.2.6] - 2026-08-18

### Added

- Rates embed **Subscribe** (green) / **Unsubscribe** (red) buttons assign or remove the guild's rate-alert role
- Buttons persist on `/rates` and automatic rate-change posts
- Deploy marker `v1.2.6`

## [1.2.5] - 2026-08-18

### Added

- DM `RESTART_NOTIFY_USER_ID` when the bot is added to a Discord server (name, ID, owner, members, who added it when audit logs allow)
- Deploy marker `v1.2.5`

## [1.2.4] - 2026-08-17

### Added

- `/serverstatus` still shows occupancy + BattleMetrics uptime when the official list misses a known server (offline)
- Offline replies include **Notify me when it's up**; the bot checks every minute and pings subscribers in that channel when it returns
- Storage: `server_up_notify` (Neon / Supabase / JSON fallback)
- Deploy marker `v1.2.4`

## [1.2.3] - 2026-08-17

### Changed

- `/serverstatus` uptime graph now fills the full BattleMetrics window (default 90 days); missing hourly buckets count as online
- 7d / 30d / 90d percents fall back to averages from that series when BM include data is missing
- Deploy marker `v1.2.3`

## [1.2.2] - 2026-08-16

### Changed

- `/serverstatus` history graph now uses **BattleMetrics uptime** (downtime → % online) instead of locally sampled player counts
- Occupancy bar kept; embed shows 7d / 30d / 90d uptime when BM responds
- Requires `BATTLEMETRICS_TOKEN` (personal access token from BattleMetrics developers area)
- Removed background player sampler integration
- Deploy marker `v1.2.2`

## [1.2.1] - 2026-08-16

### Added

- `/serverstatus` graphs: occupancy bar + 24h player-count history (PNG embed image)
- Background sampler for watched ASA servers (`server_watchlist` / `server_player_samples` on Neon)
- `Pillow` for chart rendering

### Changed

- Deploy marker `v1.2.1`

## [1.2.0] - 2026-08-12

### Added

- **Bothunter** spam-trap channel (ported from [RiskyMH/honeypot](https://github.com/RiskyMH/honeypot), commands renamed)
  - `/bothunter` — configure trap channel, log channel, softban/ban/disabled, experiments
  - `/bothunter-messages` — custom warning / DM / log messages
  - Softban (ban+unban) deletes recent messages; skips owners/admins; optional DM + reinvite + timeout-first
  - Storage: JSON / Neon `bothunter_config` + `bothunter_events` / Supabase same tables

### Changed

- Primary storage is **Neon/Postgres** (`DATABASE_URL`); all Sir-5rM8 tables (rates, karma, bothunter) live there
- Deploy marker `v1.2.0`

## [1.1.0] - 2026-08-10

### Added

- Shared **Discord Bots** Supabase storage (`bot_sir5rm8` role) with JSON fallback
- JSON → Supabase and legacy Supabase → Discord Bots migration scripts
- Deploy marker + slash sync listing for easier production verification
- Restart/redeploy DM to `RESTART_NOTIFY_USER_ID` (once per process, like ALICE)
- `asyncio.to_thread` regression tests for karma/admin storage paths
- `pytest-asyncio` for async unit tests

### Changed

- Cut over from the old Sir-5rM8 Supabase project to the unified Discord Bots database
- Upgrade `supabase` client to `>=2.15` (supports `sb_secret_…` API keys)
- Port ALICE reliability patterns: defer before DB, offload sync storage, fail-fast extension load, `SyncResult` slash sync
- Lighter schema probes (`.limit(0)`); docs renamed from ALICE project label to Discord Bots
- BOT_BLUEPRINT clarifications for optional feature folders

### Removed

- Temporary `/migrate-json-to-db` and `/migrate-old-supabase-to-db` slash commands (CLI scripts retained)
- `.env.example` (configure `.env` / host vars directly)

## [1.0.0] - 2025-02

### Added

- Structured multi-server data storage under `data/`
- Per-guild configuration for rate notifications
- Versioned config schema for future migrations
- Rate monitoring: parse by key name (robust to config format changes)
- Rate monitoring: compare parsed values only (ignores formatting/comment changes)
- Rate monitoring: "changed" indicator in embed when rates change
- HTTP retries (3 attempts, 2s delay) for rate fetches
- Single message for rate notifications (embed + role ping combined)

### Removed

- Karma system (to be rebuilt later)
- XP & Giveaway system (to be rebuilt later)
- Message content intent (no longer required)

### Changed

- Rate notification data now stored in `data/config.json` with guild-keyed structure
- Rate change state stored in `data/rate_state/previous_values.json` (parsed dict, not raw text)
- Improved error handling for rate notifications (skips missing channels/roles gracefully)
- `/rates` command now uses key-based parsing and retries

### Restructure (2025-02)

- **utils/asa.py** — ASA API client (find_server, fetch_current_rates, HTTP retries)
- **utils/constants.py** — Shared RATE_DISPLAY, RATE_KEYS, HTTP settings
- **utils/config.py** — All URLs, paths (PROJECT_ROOT, DATA_DIR)
- **utils/functions.py** — Orchestration layer (thin wrapper over asa + storage)
- **utils/storage.py** — Uses config.DATA_DIR for robust paths
- **Admin** — Response before channel message; `/sync` slash command (owner); improved error handler
- **requirements.txt** — Added
