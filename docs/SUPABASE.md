# Supabase setup (unified Discord Bots project)

Sir-5rM8 shares the **Discord Bots** Supabase project with Scumtopia-Bot and ALICE. Karma and rate tables live in the same database; this bot uses the **`bot_sir5rm8`** Postgres role (not `service_role`).

**Runbook:** [ALICE/docs/UNIFIED_SUPABASE.md](../ALICE/docs/UNIFIED_SUPABASE.md)

| Item | Value |
|------|-------|
| Project | Discord Bots (`msksvvopixdaqhvdewvw`) |
| URL | `https://msksvvopixdaqhvdewvw.supabase.co` |
| Tables | `guild_rate_notifications`, `rate_state`, `karma_*` |
| Schema SQL | [ALICE/supabase/merge_other_bots_schema.sql](../ALICE/supabase/merge_other_bots_schema.sql) |
| Roles SQL | [ALICE/supabase/bot_roles.sql](../ALICE/supabase/bot_roles.sql) |

## 1. Schema (already on Discord Bots project)

If bootstrapping a **new** project, run the ALICE repo `schema.sql`, then `merge_other_bots_schema.sql`, then `bot_roles.sql` in the SQL Editor.

Local reference copy: [`supabase/schema.sql`](../supabase/schema.sql).

## 2. Environment variables

In `.env` on the machine that runs the bot:

```env
SUPABASE_URL=https://msksvvopixdaqhvdewvw.supabase.co
SUPABASE_SERVICE_KEY=<JWT with role=bot_sir5rm8>
```

Mint the JWT from the ALICE repo (requires project JWT secret from Dashboard → Settings → API):

```bash
cd ../ALICE
export SUPABASE_JWT_SECRET='...'
python scripts/mint_bot_jwt.py --role bot_sir5rm8
```

Create `.env` on the bot host. **Do not** use the real `service_role` key on the bot host.

If either Supabase variable is missing, the bot falls back to **JSON files** under `data/`.

## 3. Migrate data from JSON files

If the bot ran with file storage, migrate once after `.env` points at Discord Bots:

```bash
python scripts/migrate_json_to_supabase.py          # dry run
python scripts/migrate_json_to_supabase.py --apply
```

### What maps where

| JSON source | Supabase table |
|-------------|----------------|
| `config.json` → `guilds.*.rate_notifications` | `guild_rate_notifications` |
| `config.json` → `karma.balances` | `karma_balances` |
| `config.json` → `karma.cooldowns` | `karma_cooldowns` |
| `config.json` → `karma.cooldown_hours` / `history_limit` | `karma_global_settings` |
| `karma_history.jsonl` (+ legacy `karma.history` in config) | `karma_events` |
| `rate_state/previous_values.json` | `rate_state.previous_rates` |

### Steps

1. **Stop the bot** during migration.
2. **Set Supabase env vars** (section 2) with `bot_sir5rm8` JWT.
3. **Dry run:** `python scripts/migrate_json_to_supabase.py`
4. **Apply:** `python scripts/migrate_json_to_supabase.py --apply`
5. **Start the bot** — expect `Supabase connection OK` in logs.
6. **Smoke test:** `/manage_karma action:check`, `/rate_channel_status`.

### Rollback

Remove or comment out `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env` and restart — the bot falls back to JSON files in `data/`.

## 4. Old Sir-5rM8 Supabase project

Project `pplxciubfymklbpvuill` can be **paused or deleted** after cutover. See the ALICE repo unified docs for backup/retire steps.

## 5. Dependencies

```bash
pip install -r requirements.txt
```

`supabase` is listed in `requirements.txt`.
