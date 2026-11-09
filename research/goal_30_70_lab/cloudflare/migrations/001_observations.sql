-- Raw factual observations only. No outcomes, prices, personal data or profit estimates.
CREATE TABLE IF NOT EXISTS live_observations(
  match_id TEXT NOT NULL,
  league TEXT NOT NULL,
  minute INTEGER NOT NULL CHECK(minute BETWEEN 30 AND 70),
  score TEXT NOT NULL,
  pressure REAL,
  shots_on REAL,
  big_chances REAL,
  observed_at TEXT NOT NULL,
  polled_at TEXT NOT NULL,
  PRIMARY KEY(match_id,minute,observed_at)
);
CREATE INDEX IF NOT EXISTS ix_live_observations_observed_at ON live_observations(observed_at);
-- Retention jobs should purge entries > 7 days, once the pilot is activated.
