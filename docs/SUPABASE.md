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

**URL format:** must be the full project URL, for example:

```env
SUPABASE_URL=https://abcdefghijklmnop.supabase.co
```

Do not use only the project ref, a database hostname, or a URL without `https://`.

### Troubleshooting: `ConnectError: Name or service not known`

This means the bot could not resolve or reach the hostname in `SUPABASE_URL`.

1. Copy **Project URL** again from Supabase → **Project Settings → API**.
2. On the bot host, confirm `.env` has no extra quotes or spaces and was saved after editing.
3. Restart the bot and check the console for `Supabase connection OK` or `Supabase connection failed`.
4. If the server cannot reach the internet (some hosts block outbound DNS), remove both Supabase env vars to use JSON files until networking is fixed.

## 4. Migrate data (optional)

If you already have `data/config.json` and `data/karma_history.jsonl`, copy balances and guild settings manually or with a one-off script. New installs can start empty in Supabase.

## 5. Dependencies

```bash
pip install -r requirements.txt
```

`supabase` is listed in `requirements.txt`.
