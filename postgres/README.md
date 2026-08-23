# Postgres setup

Sir-5rM8 stores state in **Postgres** via `DATABASE_URL`. When set, it takes
priority over Postgres REST and JSON file storage.

## 1. Create a database

Create a Postgres database and copy the **connection string** (prefer a pooled
URL for the long-running bot process).

## 2. Environment

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
TOKEN=...
```

With `DATABASE_URL` set, Postgres REST vars are ignored by the bot.

## 3. Schema + data migration

```bash
pip install -r requirements.txt

# Create tables
python scripts/migrate_to_postgres.py --apply-schema

# Preview rows that will be copied from Postgres REST
python scripts/migrate_to_postgres.py

# Copy (requires POSTGREST_URL + POSTGREST_KEY still set for export)
python scripts/migrate_to_postgres.py --apply
```

Schema source: [`postgres/schema.sql`](schema.sql).

If you already applied an older schema, re-run `--apply-schema` after upgrades that add tables
(e.g. bothunter, `server_up_notify`, `guild_ark_notifications`). `CREATE TABLE IF NOT EXISTS` is safe to re-run.

## 4. Dedicated Railway object cache (optional)

Provision a separate Railway bucket for Sir-5rM8 (for example,
`sir-5rm8-state`). Do not reuse ALICE's bucket or credentials. On the Sir-5rM8
bot service, add Variable References from the dedicated resource:

```env
STORAGE_ENDPOINT=https://storage.railway.app
STORAGE_REGION=auto
STATE_BUCKET=${{sir-5rm8-state.BUCKET}}
STATE_ACCESS_KEY_ID=${{sir-5rm8-state.ACCESS_KEY_ID}}
STATE_SECRET_ACCESS_KEY=${{sir-5rm8-state.SECRET_ACCESS_KEY}}
```

Or, after linking the bot service, run:

```bash
scripts/railway_state_bucket.sh sir-5rm8-state
```

Sir-5rM8 writes the official-list snapshot and database cache envelopes under
`cache/`, and sticky ids under `state/`. These objects survive ephemeral disk,
but Postgres remains authoritative. Persisted database copies can serve during
the short startup grace and are then reconciled from Postgres in the
background.

## 5. Restart the bot

Expect:

```
Storage backend: Postgres
Postgres connection OK
Schema OK: ...
```

## 6. Rollback

Remove `DATABASE_URL` and restore Postgres REST vars (or leave unset for JSON files).
