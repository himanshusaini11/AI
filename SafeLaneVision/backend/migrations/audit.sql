CREATE TABLE IF NOT EXISTS request_audit (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  device_id TEXT,
  method TEXT NOT NULL,
  path TEXT NOT NULL,
  status INT NOT NULL,
  ms INT NOT NULL,
  ip TEXT,
  meta JSONB
);
CREATE INDEX IF NOT EXISTS request_audit_ts_idx ON request_audit(ts DESC);