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

# Create tables + karma RPCs
python scripts/migrate_to_postgres.py --apply-schema

# Preview rows that will be copied from Postgres REST
python scripts/migrate_to_postgres.py

# Copy (requires POSTGREST_URL + POSTGREST_KEY still set for export)
python scripts/migrate_to_postgres.py --apply
```

Schema source: [`postgres/schema.sql`](schema.sql).

If you already applied an older schema, re-run `--apply-schema` after upgrades that add tables
(e.g. bothunter, `server_up_notify`, `guild_ark_notifications`). `CREATE TABLE IF NOT EXISTS` is safe to re-run.

## 4. Restart the bot

Expect:

```
Storage backend: Postgres
Postgres connection OK
Schema OK: ...
```

## 5. Rollback

Remove `DATABASE_URL` and restore Postgres REST vars (or leave unset for JSON files).
