# Neon / Postgres setup

Sir-5rM8 can use **Neon** (or any Postgres) via `DATABASE_URL`. When set, it takes
priority over Supabase and JSON file storage.

## 1. Create a Neon database

In the [Neon console](https://console.neon.tech/), create a project and copy the
**connection string** (prefer the pooled `-pooler` URL for the bot).

## 2. Environment

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
TOKEN=...
```

Optional alias: `NEON_DATABASE_URL` (same meaning).

With `DATABASE_URL` set, `SUPABASE_*` vars are ignored by the bot.

## 3. Schema + data migration from Supabase

```bash
pip install -r requirements.txt

# Create tables + karma RPCs on Neon
python scripts/migrate_supabase_to_neon.py --apply-schema

# Preview rows that will be copied from Supabase
python scripts/migrate_supabase_to_neon.py

# Copy (requires SUPABASE_URL + SUPABASE_SERVICE_KEY still set for export)
python scripts/migrate_supabase_to_neon.py --apply
```

Schema source: [`neon/schema.sql`](schema.sql) (same tables as the old Supabase schema).

If you already applied an older schema, re-run `--apply-schema` after upgrades that add tables
(e.g. bothunter). `CREATE TABLE IF NOT EXISTS` is safe to re-run.

## 4. Restart the bot

Expect:

```
Storage backend: Postgres/Neon
Postgres connection OK
Schema OK: ...
```

## 5. Rollback

Remove `DATABASE_URL` / `NEON_DATABASE_URL` and restore `SUPABASE_*` (or leave unset for JSON files).
