# Supabase setup

The bot can store rate notifications, karma, and rate-check state in **Supabase (PostgreSQL)** instead of local JSON files.

## 1. Create a project

Create a project at [supabase.com](https://supabase.com) and open **SQL Editor**.

## 2. Apply the schema

Run the contents of [`supabase_schema.sql`](supabase_schema.sql) in a new query, then **Run**.

If you already applied an older version of the schema, run the file again — the `CREATE OR REPLACE FUNCTION` blocks at the bottom are safe to re-apply and are required for atomic karma updates.

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

## 4. Migrate data from JSON files

If the bot already ran with file storage, you have data under `data/` that is **not** moved automatically when you add Supabase env vars. Migrate it once with the script below.

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

1. **Apply the schema** (section 2) if you have not already — including the karma RPC functions at the bottom of the SQL file.

2. **Stop the bot** so it is not writing to JSON while you migrate.

3. **Set Supabase env vars** in `.env` (section 3). The migration script needs them; the bot does too once you switch.

4. **Dry run** — shows counts without writing:

   ```bash
   python scripts/migrate_json_to_supabase.py
   ```

5. **Apply migration**:

   ```bash
   python scripts/migrate_json_to_supabase.py --apply
   ```

   If Supabase already has rows (e.g. you tested first), add `--force` to upsert settings/balances/cooldowns/guilds and append history events again.

6. **Verify** in Supabase → **Table Editor** that balances, guild notifications, and event counts look right.

7. **Start the bot** with both `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` set. On startup you should see:

   ```text
   Storage backend: Supabase (https://....supabase.co)
   Supabase connection OK
   ```

8. **Smoke test** — `/manage_karma action:check`, `/rate_channel_status`, and (if configured) wait for or trigger a rate check.

9. **Keep JSON as backup** until you are confident. Archive `data/config.json`, `data/karma_history.jsonl`, and `data/rate_state/` somewhere safe; the bot ignores them once Supabase env vars are set.

### Rollback

Remove or comment out `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env` and restart — the bot falls back to JSON files in `data/`. Your original files are unchanged by the migration script.

## 5. Dependencies

```bash
pip install -r requirements.txt
```

`supabase` is listed in `requirements.txt`.
