CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  episode INTEGER NOT NULL,
  timecode TEXT NOT NULL,
  original TEXT NOT NULL,
  suggestion TEXT,
  comment TEXT,
  anchor_json TEXT NOT NULL,
  source_url TEXT,
  ip_hash TEXT
);

CREATE INDEX IF NOT EXISTS reports_status_created_at
  ON reports(status, created_at DESC);

CREATE INDEX IF NOT EXISTS reports_ip_hash_created_at
  ON reports(ip_hash, created_at DESC);
