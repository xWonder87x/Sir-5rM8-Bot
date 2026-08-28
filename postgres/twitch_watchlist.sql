-- Persisted Twitch logins and go-live ping dedupe for /streamers.
-- Apply: psql "$DATABASE_URL" -f postgres/twitch_watchlist.sql

CREATE TABLE IF NOT EXISTS twitch_stream_pinged (
  twitch_login TEXT PRIMARY KEY,
  stream_id    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS twitch_stream_watchlist (
  twitch_login TEXT PRIMARY KEY,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
