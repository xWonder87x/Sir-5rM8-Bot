# BOT_BLUEPRINT.md

**Universal architecture and strategy for Discord bots** built with **Python 3.10+**, **discord.py** (slash/interactions only), and **Supabase/Postgres**.

Copy this file into every bot repo. Pair it with a bot-specific **`AGENTS.md`** (commands, load order, feature env vars for that bot). **ALICE** is the reference implementation — see its `AGENTS.md` for a filled-in example.

---

## Non-negotiable rules

1. **Slash commands only** for users. Prefix `!` exists only because discord.py requires it internally — do not add user-facing prefix commands.
2. **Centralize IDs and tunables** in `config.py`. Never scatter guild/channel/role literals in cogs.
3. **Secrets in environment variables** (`.env` locally, host dashboard in production). Never commit tokens or keys.
4. **All persistence through the `db` package** — no raw SQL or ad hoc Supabase calls in command files.
5. **Shared non-cog logic in `functions/` or `commands/common/`** — not copy-pasted across cogs.
6. **`logging` only** for runtime behaviour — no `print`.
7. **Keep `README.md` in sync** when user-visible commands change.
8. **Prefer `command_sync.sync_application_commands`** over ad hoc `bot.tree.sync()` so guild-scoped duplicates stay cleared where configured.

---

## Standard project layout

```
.
├── main.py                 # Entry: bot client, extension load order, login/429 retry, global listeners
├── config.py               # IDs, feature flags, env reads — no secrets hard-coded
├── db/                     # Database package (domain-split; __init__ re-exports full API)
│   ├── __init__.py
│   ├── _base.py            # Client, _tbl, EXPECTED_SCHEMA, check_schema, use_supabase
│   └── <domain>.py         # One module per table group (economy, warnings, …)
├── functions/              # Shared bot helpers (not tied to one cog)
│   ├── __init__.py         # Re-exports public API: functions.<name>
│   ├── _base.py            # Logger, locks, tiny shared state
│   ├── checks.py           # Guild/feature guard helpers for slash handlers
│   └── <concern>.py        # e.g. economy.py, ledger.py
├── commands/
│   ├── common/             # Cross-cog helpers — NO cog, NO setup()
│   │   ├── state.py        # Persisted message-id JSON load/save (data/*.json)
│   │   └── sticky.py       # StickyMessage manager (recover / ensure / clear / repost)
│   ├── core/               # /help, /sync-commands, maintenance, command_sync helpers
│   ├── mod/                # Moderation, auctions, …
│   ├── economy/            # Coins/XP — may be a package (see below)
│   ├── community/          # Social/utility features
│   ├── partner/            # Partner-specific flows (if applicable)
│   ├── integrations/       # External APIs (AI, Twitch, …)
│   └── <feature>/          # Large features get their own area
├── supabase/
│   ├── schema.sql          # Canonical DDL — run in Supabase SQL Editor
│   ├── README.md           # How to apply schema, migration notes
│   └── supabase_probe.py   # Standalone read-only connection ping (no db import)
├── scripts/                # Offline verification scripts (no Discord token required)
├── data/                   # Runtime JSON state (gitignored); created by main.py
├── Dockerfile              # Production: CMD ["python", "main.py"]
├── requirements.txt
├── README.md               # Human command catalog + setup
├── BOT_BLUEPRINT.md        # This file — universal architecture (copy to every bot)
└── AGENTS.md               # Bot-specific agent notes (commands, load order, env vars)
```

| Path | Role |
|------|------|
| `main.py` | `commands.Bot`, staggered login / 429 exit+restart, `on_ready` extension load list, maintenance gate, global listeners |
| `config.py` | `CHANNELS`, `ROLES`, guild IDs, timeouts, message templates — read env with `os.environ.get` |
| `db/` | All Supabase/Postgres access; `EXPECTED_SCHEMA` + `check_schema()` in `db/_base.py` |
| `functions/` | Guards, shared business logic, audit logging — anything used by 2+ cogs |
| `commands/<area>/` | One or more cogs; each exposes `async def setup(bot)` |
| `commands/common/` | `state.py`, `sticky.py`, `logging.py` (Supabase log handler) — never loaded as an extension |
| `commands/core/extensions.py` | **`COG_EXTENSIONS`** — single source of truth for extension load order |
| `supabase/schema.sql` | Source of truth for table DDL |
| `scripts/` | `verify_*.py` smoke tests runnable without the bot online |

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Language | Python 3.10+ (`.python-version` for pyenv) |
| Discord | `discord.py` — interactions / app commands only |
| Database | Postgres via Supabase (or self-hosted with same schema discipline) |
| Config | `config.py` for IDs/tunables; `.env` / host vars for secrets |
| Deploy | Docker (`python:3.12-slim`) on Railway or similar worker host |
| Logging | Python `logging`; optional remote handler (e.g. Supabase `bot_logs`) |

---

## Layer responsibilities

### `main.py`

- Load `.env`, validate required env (exit early with a clear message if missing).
- Configure logging (console + optional remote handler).
- Create `commands.Bot` with appropriate intents.
- Load extensions in a **fixed, documented order** (listed in that bot's `AGENTS.md`).
- Sync slash commands once after cogs load; retry global sync on later `on_ready` if the first attempt failed.
- On Discord **429** at login: wait, `sys.exit(1)` — let Docker/Railway restart policy retry (see `LOGIN_RETRY_ATTEMPT`).
- Stagger startup (`time.sleep` jitter) to avoid hammering Discord on crash loops.

### `config.py`

- Dicts/constants for Discord IDs (`CHANNELS`, `ROLES`, `CATEGORIES`, guild allowlists).
- Feature tunables (cooldowns, batch sizes, message templates).
- Optional env overrides with sensible defaults.
- **`DATA_DIR`** — path for runtime JSON (sticky message ids, etc.).

### `db/` package

Split by **domain** (one file per table group). Keep each module focused; aim for **< ~400 lines** per file.

| Module | Typical contents |
|--------|------------------|
| `_base.py` | `_get_client()`, `_tbl()`, `_parse_dt()`, `use_supabase()`, `EXPECTED_SCHEMA`, `check_schema()`, package logger |
| `<domain>.py` | CRUD/query helpers for related tables |
| `__init__.py` | Re-export **everything** callers use so `import db` / `db.foo()` never breaks |

**Rules:**

- Add DDL to `supabase/schema.sql` first.
- Update `db/_base.py::EXPECTED_SCHEMA` to match.
- Implement helpers in the appropriate domain module.
- Use `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` for idempotent migrations.
- Offload synchronous Supabase calls from async handlers with `asyncio.to_thread(...)`.

**When to split:** a single `db.py` is fine for small bots. Once it exceeds ~400–500 lines or mixes unrelated tables, split into `db/` with `__init__.py` re-exports so callers keep using `import db`.

### `functions/` package

Split by **concern** (checks, ledger, economy, …). Same re-export pattern as `db/`.

| Module | Typical contents |
|--------|------------------|
| `_base.py` | Shared logger, threading locks for atomic read-modify-write |
| `checks.py` | `require_guild(interaction)`, feature-specific guards |
| `<concern>.py` | Business logic shared across cogs |
| `__init__.py` | Explicit `__all__` + re-exports — callers use `functions.<name>` only |

Do **not** put Discord UI (views, modals) here — those belong in `commands/`.

### `commands/<area>/`

Each **extension** is a Python module or package loaded via `await bot.load_extension("commands.<area>.<module>")`.

**Single-file cog** (simple features):

```python
class MyCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None: ...

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MyCog(bot))
```

**Package cog** (large features — split when a file exceeds ~400–500 lines or mixes concerns):

```
commands/<area>/<feature>/
├── __init__.py    # setup() registers cog(s), persistent views, cross-cog hooks
├── cog.py         # Slash commands (commands.Cog)
├── views.py       # Buttons, modals, select menus
├── sticky.py      # Sticky-channel cogs (background tasks) — if needed
├── _store.py      # Persistence, parsing, reconcile (pure + db) — if needed
└── _shared.py     # Constants, embed builders, matchers — no setup()
```

| Split | Goes in |
|-------|---------|
| Slash handlers | `cog.py` or main feature module |
| Discord UI components | `views.py` |
| DB load/save, parsing, reconcile | `_store.py` |
| Constants, embed builders, matchers | `_shared.py` |
| Background sticky channels | `sticky.py` |
| Extension registration | `__init__.py` → `setup(bot)` |

### `commands/common/`

Helpers used by multiple cogs. **Never** has `setup()` and **never** loaded as an extension.

- **`state.py`** — `load_persisted_message_id(path)` / `save_persisted_message_id(path, id)` for `data/*.json`.
- **`sticky.py`** — `StickyMessage` class:
  - `recover(channel)` — confirm tracked id or scan history with a matcher
  - `ensure(channel, embed, view=None)` — edit in place or post fresh
  - `clear()` — forget id, delete state file
  - `delete_and_repost(channel, msg, embed, view=None)` — remove wrong sticky, post clean one

Cogs keep embed/view building and sweep logic; delegate mechanics to `StickyMessage`.

---

## Cog & task conventions

```python
async def cog_load(self) -> None:
    if self._channel_id:
        self._my_loop.start()

def cog_unload(self) -> None:
    self._my_loop.cancel()

@tasks.loop(minutes=1)
async def _my_loop(self) -> None:
    try:
        ...
    except Exception:
        logger.exception("my_loop failed")

@_my_loop.before_loop
async def _before_my_loop(self) -> None:
    await self.bot.wait_until_ready()
```

- Start background work in **`cog_load`**, cancel in **`cog_unload`**.
- Use **`asyncio.get_running_loop().create_task(...)`** inside async hooks — not `self.bot.loop` (fragile before connect).
- Wrap loop bodies in **`try/except`** + `logger.exception` so one failure does not kill the task silently.
- **`commands/common/logging.py`** — optional remote log handler (e.g. Supabase `bot_logs`); wire from `main.py` after `load_dotenv()`.
- Register **persistent views** in `setup()` via `bot.add_view(...)` when buttons must survive restarts.
- One-shot startup reconcile: `await bot.wait_until_ready()` inside the task, then run.

---

## Extension load order

Order matters for slash registration, persistent views, and log clarity. Define the list once in **`commands/core/extensions.py`**:

```python
COG_EXTENSIONS: list[tuple[str, str]] = [
    ("commands.core.help", "Help cog loaded"),
    ...
]

async def load_all_extensions(bot: commands.Bot) -> None: ...
```

`main.py` calls `load_all_extensions(bot)` on first `on_ready`. Mirror the list in that bot's **`AGENTS.md`**.

**Rules when adding a cog:**

1. Add `async def setup(bot)` to the module/package.
2. Append to **`COG_EXTENSIONS`** in `commands/core/extensions.py`.
3. Document in that bot's **`AGENTS.md`**.
4. Update **`README.md`** command catalog.
5. If load order depends on another cog (shared views, DB seed), place it **after** the dependency.

---

## Slash command sync

- **`commands/core/command_sync.py`** — `sync_application_commands(bot)` clears stale guild-scoped commands where configured, then global sync.
- Startup: sync once after all cogs load; retry on later `on_ready` if global sync failed (rate limit).
- **`/sync-commands`** (admin) — force sync; works during maintenance mode.
- Optional **`SLASH_SYNC_GUILD_IDS`** in env/config for extra guild-scope clears.
- Register commands **globally** unless there is a deliberate reason for guild scope.

---

## Database workflow

1. Design table → add **`CREATE TABLE IF NOT EXISTS`** to `supabase/schema.sql`.
2. Add table + columns to **`db/_base.py::EXPECTED_SCHEMA`**.
3. Implement helpers in **`db/<domain>.py`**.
4. Note the change in **`supabase/README.md`**.
5. Validate: `db.check_schema()` (requires live `SUPABASE_*` in env).

Never skip step 2 — `check_schema()` is the guardrail against drift.

For a **new bot**, design tables for that bot's features only. Do **not** copy another bot's tables unless you explicitly share a database.

---

## Environment variables

### Required (all bots using this stack)

| Variable | Purpose |
|----------|---------|
| `TOKEN` | Discord bot token |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` or `SUPABASE_KEY` | Service role key (backend only) |

### Common optional

| Variable | Purpose |
|----------|---------|
| `SLASH_SYNC_GUILD_IDS` | Comma-separated guild IDs for guild-scope command clear |
| `LOGIN_RETRY_ATTEMPT` | **Internal** — 429 retry counter; do not set manually |

Bot-specific optional vars (AI keys, Twitch, Google Sheets, etc.) belong in that bot's **`README.md`** and **`AGENTS.md`**.

---

## Local setup

```bash
python3.10 --version          # 3.10+ required (.python-version in repo for pyenv)
pip install -r requirements.txt
# create .env with TOKEN, SUPABASE_URL, SUPABASE_SERVICE_KEY
python main.py
```

---

## Validation (run before every PR / deploy)

### 1. Syntax

```bash
python -m compileall main.py commands db config.py functions
```

### 2. Lint (project source only — exclude `.venv`)

```bash
python -m pyflakes main.py config.py db functions commands scripts supabase
```

### 3. Extension smoke test

Load every extension into a bare `commands.Bot` and confirm zero failures. All slash commands should register with no duplicate names.

### 4. Schema (when DB touched)

```bash
python -c "import db; print(db.check_schema())"
```

All tables should return `(name, True, None)`.

### 5. Feature scripts

Run relevant `scripts/verify_*.py` for the area you changed.

### 6. Reference resolution (after package splits)

Grep for `db.<name>` and `functions.<name>` usages; confirm every name exists on the package via `hasattr`.

### 7. Pytest (recommended)

```bash
pip install -r requirements-dev.txt
pytest
```

Offline tests live in `tests/` (extension load, sticky helper, `EXPECTED_SCHEMA` shape). Feature scripts in `scripts/verify_*.py` for integration checks without Discord.

### 8. Scaffold a new bot repo

From ALICE (or any repo with `BOT_BLUEPRINT.md`):

```bash
python scripts/scaffold_bot.py /path/to/NewBot --name "New Bot"
```

Creates layout + stub files; copy `BOT_BLUEPRINT.md`, fill in `AGENTS.md`, add cogs to `COG_EXTENSIONS`.

---

## Deployment (Docker / Railway)

- **`Dockerfile`**: `FROM python:3.12-slim`, `CMD ["python", "main.py"]`, `PYTHONUNBUFFERED=1`.
- **Railway**: connect repo, set env vars in dashboard, deploy on push to `main`.
- **"Stopping Container"** during deploy is normal — Railway stops the old instance before starting the new one. If the bot is online in Discord after ~1–2 minutes, the deploy succeeded.
- **Crash loop?** Check deploy logs for: missing env vars, import errors, Discord 429 (bot exits and Railway restarts — usually clears).
- **No HTTP port required** — Discord bots are outbound-only; Railway works fine with a worker-style service.

---

## Change checklist

When adding or modifying features in any bot:

- [ ] IDs/tunables in `config.py` (not literals in cogs)
- [ ] DB changes: `schema.sql` + `EXPECTED_SCHEMA` + domain module + `supabase/README.md`
- [ ] Cog added to **`commands/core/extensions.py`** (`COG_EXTENSIONS`)
- [ ] `README.md` updated if user-visible commands changed
- [ ] Bot's `AGENTS.md` updated if load order, modules, or feature env vars changed
- [ ] Validation steps above pass
- [ ] No secrets committed

---

## Briefing a coding agent

### New bot (greenfield)

> I'm starting a brand-new Discord bot. Follow **`BOT_BLUEPRINT.md`**: Python 3.10+, discord.py slash-only, `main.py` + `config.py` + `db/` package + `functions/` package + `commands/<area>/` cogs + `supabase/schema.sql` + `EXPECTED_SCHEMA`. Create a bot-specific **`AGENTS.md`** for commands and load order. Do **not** copy commands from my other bots. For v1, here are the features I want: … (list). Create skeleton, requirements, `.env` docs, empty cogs with `setup()`, and README command section.

### Existing bot

> Follow **`BOT_BLUEPRINT.md`** for architecture and validation. Follow this repo's **`AGENTS.md`** for bot-specific commands, load order, and env vars. Preserve public import paths (`import db`, `import functions`, extension names). Split large files into packages with `__init__.py` re-exports rather than changing callers.

### Starting from ALICE as template

> Copy **`BOT_BLUEPRINT.md`** and use **ALICE** (`AGENTS.md` + repo structure) as the reference implementation. Strip ALICE-specific cogs/tables/commands; keep the package layout and conventions.

---

## Sticky messages & background tasks (pattern)

When a bot needs a persistent embed in a channel:

1. Store message id in `data/<feature>_message.json` via `commands/common/state.py`.
2. Use `commands/common/sticky.StickyMessage` for recover/ensure/repost.
3. Run verify/refresh loops with `@tasks.loop` in a dedicated cog or `sticky.py`.
4. Optional: purge unrelated messages in the same channel (cog-specific sweep logic).

State can also live in the DB (e.g. leaderboard message ids) when multiple instances or durability matters.

---

## Package split decision guide

| Situation | Action |
|-----------|--------|
| File < ~400 lines, single concern | Keep as one module |
| File > ~500 lines or mixed UI + DB + tasks | Split into package |
| Helper used by 2+ cogs, no Discord UI | `functions/` or `commands/common/` |
| All DB access | `db/<domain>.py` only |
| After split | Re-export from `__init__.py`; grep callers; run extension smoke test |

Preserve **`import db`**, **`import functions`**, and extension paths — never force a repo-wide import rewrite unless intentional.
