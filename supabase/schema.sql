-- Sir-5rM8 — unified Supabase on the Discord Bots project (msksvvopixdaqhvdewvw).
-- Canonical apply path: ALICE/supabase/merge_other_bots_schema.sql + bot_roles.sql
-- Runbook: ../ALICE/docs/UNIFIED_SUPABASE.md
-- Bot credential: JWT with role=bot_sir5rm8 (mint via ALICE/scripts/mint_bot_jwt.py)
--
-- Legacy note: this file is kept for reference. Tables may omit public. prefix; merge SQL uses public.

-- Sir-5rM8 — run this in Supabase SQL Editor (Dashboard → SQL → New query)
-- Then set SUPABASE_URL and SUPABASE_SERVICE_KEY in the bot’s .env (per-bot JWT, not service_role).

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

-- Karma settings (single row)
CREATE TABLE IF NOT EXISTS karma_global_settings (
  id             SMALLINT PRIMARY KEY CHECK (id = 1),
  cooldown_hours INT NOT NULL DEFAULT 24,
  history_limit  INT NOT NULL DEFAULT 10
);

INSERT INTO karma_global_settings (id, cooldown_hours, history_limit)
VALUES (1, 24, 10)
ON CONFLICT (id) DO NOTHING;

-- Per-user karma totals (global across guilds)
CREATE TABLE IF NOT EXISTS karma_balances (
  user_id TEXT PRIMARY KEY,
  balance INT NOT NULL DEFAULT 0
);

-- Cooldown: last time giver gave karma to receiver
CREATE TABLE IF NOT EXISTS karma_cooldowns (
  giver_id    TEXT NOT NULL,
  receiver_id TEXT NOT NULL,
  last_given  TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (giver_id, receiver_id)
);

-- Append-only style event log (history + audit)
CREATE TABLE IF NOT EXISTS karma_events (
  id         BIGSERIAL PRIMARY KEY,
  user_id    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  action     TEXT NOT NULL,
  amount     INT NOT NULL DEFAULT 1,
  by_name    TEXT,
  giver_id   TEXT,
  admin_id   TEXT,
  reason     TEXT
);

CREATE INDEX IF NOT EXISTS idx_karma_events_user_created
  ON karma_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_karma_events_remove_created
  ON karma_events (action, created_at DESC)
  WHERE action = 'remove';

-- Optional: tighten API access — the Discord bot uses the service_role key and bypasses RLS.
-- If you ever use the anon key from clients, add RLS policies here.

-- Atomic karma balance updates (used by storage_supabase.py via RPC)
CREATE OR REPLACE FUNCTION karma_increment_balance(p_user_id TEXT)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  new_balance INT;
BEGIN
  INSERT INTO karma_balances (user_id, balance)
  VALUES (p_user_id, 1)
  ON CONFLICT (user_id) DO UPDATE
    SET balance = karma_balances.balance + 1
  RETURNING balance INTO new_balance;
  RETURN new_balance;
END;
$$;

CREATE OR REPLACE FUNCTION karma_decrement_balance(p_user_id TEXT)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  new_balance INT;
BEGIN
  UPDATE karma_balances
  SET balance = balance - 1
  WHERE user_id = p_user_id AND balance > 0
  RETURNING balance INTO new_balance;
  RETURN new_balance;
END;
$$;

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
