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

-- Bothunter (spam trap channel — port of RiskyMH/honeypot, renamed)
CREATE TABLE IF NOT EXISTS bothunter_config (
  guild_id         TEXT PRIMARY KEY,
  channel_id       TEXT,
  log_channel_id   TEXT,
  action           TEXT NOT NULL DEFAULT 'softban',
  warning_msg_id   TEXT,
  experiments      JSONB NOT NULL DEFAULT '[]'::jsonb,
  warning_message  TEXT,
  dm_message       TEXT,
  log_message      TEXT,
  reinvite_code    TEXT
);

CREATE TABLE IF NOT EXISTS bothunter_events (
  id         BIGSERIAL PRIMARY KEY,
  guild_id   TEXT NOT NULL,
  user_id    TEXT NOT NULL,
  channel_id TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bothunter_events_guild
  ON bothunter_events (guild_id);

CREATE INDEX IF NOT EXISTS idx_bothunter_events_guild_channel
  ON bothunter_events (guild_id, channel_id);

-- Server player sampling (for /serverstatus history graph)
CREATE TABLE IF NOT EXISTS server_watchlist (
  server_key    TEXT PRIMARY KEY,
  session_name  TEXT,
  last_queried  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS server_player_samples (
  id           BIGSERIAL PRIMARY KEY,
  server_key   TEXT NOT NULL REFERENCES server_watchlist (server_key) ON DELETE CASCADE,
  num_players  INT NOT NULL,
  max_players  INT NOT NULL,
  sampled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_server_player_samples_key_time
  ON server_player_samples (server_key, sampled_at DESC);

-- /serverstatus "Notify me when it's up" subscribers
CREATE TABLE IF NOT EXISTS server_up_notify (
  server_key    TEXT NOT NULL,
  user_id       TEXT NOT NULL,
  channel_id    TEXT NOT NULL,
  guild_id      TEXT,
  query         TEXT,
  session_name  TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (server_key, user_id, channel_id)
);

CREATE INDEX IF NOT EXISTS idx_server_up_notify_key
  ON server_up_notify (server_key);

-- Official in-game ASA notifications (cdn2.arkdedicated.com/asa/notification.html)
CREATE TABLE IF NOT EXISTS guild_ark_notifications (
  guild_id         TEXT PRIMARY KEY,
  channel_id       TEXT NOT NULL,
  last_message_id  TEXT
);

ALTER TABLE guild_ark_notifications
  ADD COLUMN IF NOT EXISTS last_message_id TEXT;

CREATE TABLE IF NOT EXISTS ark_notification_state (
  id             SMALLINT PRIMARY KEY CHECK (id = 1),
  previous_text  TEXT
);

INSERT INTO ark_notification_state (id, previous_text)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS twitch_stream_pinged (
  twitch_login TEXT PRIMARY KEY,
  stream_id    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS twitch_stream_watchlist (
  twitch_login TEXT PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
