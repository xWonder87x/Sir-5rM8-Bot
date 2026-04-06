## Cursor Cloud specific instructions

### Overview
Sir-5rM8 is a Python Discord bot for ARK: Survival Ascended communities. It is a single-service application (not a monorepo). The entry point is `main.py`.

### Running the bot
- **Start:** `python main.py` (requires `TOKEN` env var or `.env` file with `TOKEN=<discord_bot_token>`)
- The bot has a staggered startup delay (15–45s random) built into `main.py`. Set `LOGIN_RETRY_ATTEMPT=5` to bypass retry logic for quick exit during testing.
- Without a valid Discord bot token, the bot raises `ValueError("TOKEN not set...")`. This is expected.

### Storage
- Default: local JSON files in `data/`. No database needed.
- Optional: Supabase (set `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in `.env`). Schema in `docs/supabase_schema.sql`.

### Testing core functionality without a token
All non-Discord functionality can be tested directly:
```python
from utils.asa import fetch_current_rates, find_server
rates = fetch_current_rates()         # fetches live ASA rates from CDN
server = find_server('5313')          # looks up an ARK server
```
```python
from utils.storage_files import save_previous_rate_values, get_previous_rate_values
save_previous_rate_values({'XPMultiplier': '2.0'})
get_previous_rate_values()
```
Bot extensions can be loaded without connecting to Discord:
```python
import asyncio
from main import load_extensions, bot
asyncio.run(load_extensions())
```

### Linting / Tests
There is no linter or test framework configured in this repo. Basic validation is: ensure all modules import without error and core API calls succeed.

### Key gotchas
- PyNaCl/davey warnings at startup are harmless (voice is unused).
- The ARK CDN APIs (`cdn2.arkdedicated.com`) are public and require no auth.
- The `data/` directory is auto-created on first run.
