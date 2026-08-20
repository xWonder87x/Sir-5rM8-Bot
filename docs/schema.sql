-- Sir-5rM8 — unified Postgres REST on the Discord Bots project (msksvvopixdaqhvdewvw).
-- Apply postgres/schema.sql for DATABASE_URL; this file is the REST-oriented copy.
-- Bot credential: JWT with role=bot_sir5rm8
--
-- Legacy note: this file is kept for reference. Tables may omit public. prefix; merge SQL uses public.

-- Sir-5rM8 — run this in the SQL editor
-- Then set POSTGREST_URL and POSTGREST_KEY in the bot’s .env (per-bot JWT, not a superuser key).

-- Rate notification targets (one row per Discord guild)
CREATE TABLE IF NOT EXISTS guild_rate_notifications (
  guild_id   TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  role_id    TEXT NOT NULL
);

-- Single-row cache for ASA rate comparison
CREATE TABLE IF NOT EXISTS rate_state (
  id              SMALLINT PRIMARY KEY CHECK (id = 1),
  previous_rates  JSONB
);

INSERT INTO rate_state (id, previous_rates)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

-- Optional: tighten API access — the Discord bot uses a privileged API key and bypasses RLS.
-- If you ever use an anonymous key from clients, add RLS policies here.

CREATE TABLE IF NOT EXISTS guild_ark_notifications (
  guild_id   TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ark_notification_state (
  id             SMALLINT PRIMARY KEY CHECK (id = 1),
  previous_text  TEXT
);

INSERT INTO ark_notification_state (id, previous_text)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;
