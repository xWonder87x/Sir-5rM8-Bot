# Changelog

## [1.1.0] - 2026-08-10

### Added

- Shared **Discord Bots** Supabase storage (`bot_sir5rm8` role) with JSON fallback
- JSON → Supabase and legacy Supabase → Discord Bots migration scripts
- Deploy marker + slash sync listing for easier production verification
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
