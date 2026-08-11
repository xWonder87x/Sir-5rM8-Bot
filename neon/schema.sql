-- Sir-5rM8 schema for Neon / any Postgres.
-- Apply: python scripts/migrate_supabase_to_neon.py --apply-schema
-- Or: psql "$DATABASE_URL" -f neon/schema.sql

CREATE TABLE IF NOT EXISTS guild_rate_notifications (
  guild_id   TEXT PRIMARY KEY,
  channel_id TEXT NOT NULL,
  role_id    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_state (
  id              SMALLINT PRIMARY KEY CHECK (id = 1),
  previous_rates  JSONB
);

INSERT INTO rate_state (id, previous_rates)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS karma_global_settings (
  id             SMALLINT PRIMARY KEY CHECK (id = 1),
  cooldown_hours INT NOT NULL DEFAULT 24,
  history_limit  INT NOT NULL DEFAULT 10
);

INSERT INTO karma_global_settings (id, cooldown_hours, history_limit)
VALUES (1, 24, 10)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS karma_balances (
  user_id TEXT PRIMARY KEY,
  balance INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS karma_cooldowns (
  giver_id    TEXT NOT NULL,
  receiver_id TEXT NOT NULL,
  last_given  TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (giver_id, receiver_id)
);

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
