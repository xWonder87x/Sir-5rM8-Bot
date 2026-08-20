# Database setup (Discord Bots project)

Sir-5rM8 shares the **Discord Bots** Postgres project with Scumtopia-Bot and ALICE. Karma and rate tables live in the same database; this bot uses the **`bot_sir5rm8`** Postgres role.

**Runbook:** [ALICE unified database docs](../ALICE/docs/UNIFIED_SUPABASE.md)

| Item | Value |
|------|-------|
| Project | Discord Bots (`msksvvopixdaqhvdewvw`) |
| URL | `https://msksvvopixdaqhvdewvw.supabase.co` |
| Tables | `guild_rate_notifications`, `rate_state`, `guild_ark_notifications`, `ark_notification_state`, `karma_*` |
| Schema SQL | [ALICE merge schema](../ALICE/supabase/merge_other_bots_schema.sql) |
| Roles SQL | [ALICE bot roles](../ALICE/supabase/bot_roles.sql) |

Preferred runtime path is **`DATABASE_URL`** (direct Postgres). The REST URL above is only the fallback client.

## 1. Schema

If bootstrapping a **new** project, apply the ALICE repo `schema.sql`, then the merge schema, then bot roles in the SQL editor.

Local reference copy: [`postgres/schema.sql`](../postgres/schema.sql). REST-oriented copy: [`postgres/schema.rest.sql`](../postgres/schema.rest.sql).

## 2. Environment variables

Preferred (direct Postgres):

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
```

Postgres REST fallback (ignored when `DATABASE_URL` is set):

```env
POSTGREST_URL=https://msksvvopixdaqhvdewvw.supabase.co
POSTGREST_KEY=<JWT with role=bot_sir5rm8>
```

Mint the JWT from the ALICE repo (requires the project JWT secret):

```bash
cd ../ALICE
python scripts/mint_bot_jwt.py --role bot_sir5rm8
```

Create `.env` on the bot host. **Do not** use a superuser API key on the bot host.

If remote database variables are missing, the bot falls back to **JSON files** under `data/`.

## 3. Migrate data from JSON files

If the bot ran with file storage, migrate once after `.env` points at Discord Bots:

```bash
python scripts/migrate_json_to_db.py          # dry run
python scripts/migrate_json_to_db.py --apply
```

### What maps where

| JSON source | Table |
|-------------|----------------|
| `config.json` → `guilds.*.rate_notifications` | `guild_rate_notifications` |
| `config.json` → `guilds.*.ark_notifications` | `guild_ark_notifications` (JSON fallback only; JSON→DB migrate does not copy this yet) |
| `config.json` → `karma.balances` | `karma_balances` |
| `config.json` → `karma.cooldowns` | `karma_cooldowns` |
| `config.json` → `karma.cooldown_hours` / `history_limit` | `karma_global_settings` |
| `karma_history.jsonl` (+ legacy `karma.history` in config) | `karma_events` |
| `rate_state/previous_values.json` | `rate_state.previous_rates` |

### Steps

1. **Stop the bot** during migration.
2. **Set database env vars** (section 2) with `bot_sir5rm8` JWT if using REST.
3. **Dry run:** `python scripts/migrate_json_to_db.py`
4. **Apply:** `python scripts/migrate_json_to_db.py --apply`
5. **Start the bot** — expect `Postgres REST connection OK` (or `Postgres connection OK` with `DATABASE_URL`).
6. **Smoke test:** `/manage_karma action:check`, `/rate_channel_status`.

### Rollback

Remove remote database vars from `.env` and restart — the bot falls back to JSON files in `data/`.

## 4. Old Sir-5rM8 database project

Project `pplxciubfymklbpvuill` can be **paused or deleted** after cutover. See the ALICE repo unified docs for backup/retire steps.

## 5. Dependencies

```bash
pip install -r requirements.txt
```

The Postgres REST Python client is listed in `requirements.txt`.
