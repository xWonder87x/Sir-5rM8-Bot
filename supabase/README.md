# Supabase setup (unified Discord Bots project)

Sir-5rM8 shares the **Discord Bots** Supabase project with Scumtopia-Bot and ALICE. Karma and rate tables live in the same database; this bot uses the **`bot_sir5rm8`** Postgres role (not `service_role`).

**Runbook:** [ALICE/docs/UNIFIED_SUPABASE.md](../../ALICE/docs/UNIFIED_SUPABASE.md)

| Item | Value |
|------|-------|
| Project | Discord Bots (`msksvvopixdaqhvdewvw`) |
| URL | `https://msksvvopixdaqhvdewvw.supabase.co` |
| Tables | `guild_rate_notifications`, `rate_state`, `karma_*` |
| Schema SQL | [ALICE/supabase/merge_other_bots_schema.sql](../../ALICE/supabase/merge_other_bots_schema.sql) |
| Roles SQL | [ALICE/supabase/bot_roles.sql](../../ALICE/supabase/bot_roles.sql) |

## Apply schema

If bootstrapping a **new** project, run the ALICE repo `schema.sql`, then `merge_other_bots_schema.sql`, then `bot_roles.sql` in the SQL Editor.

Local reference copy: [`schema.sql`](schema.sql).

## Environment variables

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

If Supabase env vars are missing, the bot falls back to **JSON files** under `data/`.

## Verify

```bash
python supabase/supabase_probe.py
python -c "import db; print(db.check_schema())"
```

## Migrate from JSON

```bash
python scripts/migrate_json_to_supabase.py          # dry run
python scripts/migrate_json_to_supabase.py --apply
```

See also [`docs/SUPABASE.md`](../docs/SUPABASE.md) for the full migration table.
