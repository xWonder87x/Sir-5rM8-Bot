-- Sir-5rM8 — run this in Supabase SQL Editor (Dashboard → SQL → New query)
-- Then set SUPABASE_URL and SUPABASE_SERVICE_KEY in the bot’s .env (use the service_role key; keep it secret).

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
