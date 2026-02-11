# Changelog

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
