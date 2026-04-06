# Supabase setup

The bot can store rate notifications, karma, and rate-check state in **Supabase (PostgreSQL)** instead of local JSON files.

## 1. Create a project

Create a project at [supabase.com](https://supabase.com) and open **SQL Editor**.

## 2. Apply the schema

Run the contents of [`supabase_schema.sql`](supabase_schema.sql) in a new query, then **Run**.

## 3. Environment variables

In `.env` on the machine that runs the bot:

```env
SUPABASE_URL=https://xxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

- **SUPABASE_URL**: **Project Settings → API → Project URL**
- **SUPABASE_SERVICE_KEY**: **Project Settings → API → service_role** (secret; never expose in client apps or public repos)

If either variable is missing, the bot falls back to **JSON files** under `data/`.

## 4. Migrate data (optional)

If you already have `data/config.json` and `data/karma_history.jsonl`, copy balances and guild settings manually or with a one-off script. New installs can start empty in Supabase.

## 5. Dependencies

```bash
pip install -r requirements.txt
```

`supabase` is listed in `requirements.txt`.
