CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS devices (
  device_id TEXT PRIMARY KEY,
  platform TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  last_seen TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rides (
  ride_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT REFERENCES devices(device_id),
  started_at TIMESTAMPTZ, ended_at TIMESTAMPTZ,
  start_geom GEOGRAPHY(POINT), end_geom GEOGRAPHY(POINT)
);

CREATE TABLE IF NOT EXISTS frames (
  frame_id TEXT PRIMARY KEY,
  ride_id UUID REFERENCES rides(ride_id),
  ts TIMESTAMPTZ NOT NULL,
  geom GEOGRAPHY(POINT) NOT NULL,
  speed_mps REAL,
  weather JSONB,
  meta JSONB
);

CREATE TABLE IF NOT EXISTS detections (
  det_id BIGSERIAL PRIMARY KEY,
  frame_id TEXT REFERENCES frames(frame_id),
  class TEXT, score REAL,
  bbox_xyxy REAL[4],
  depth_m REAL,
  lane_offset_m REAL,
  ttc_s REAL,
  risk REAL
);

CREATE TABLE IF NOT EXISTS hazards (
  hazard_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ts TIMESTAMPTZ NOT NULL,
  geom GEOGRAPHY(POINT) NOT NULL,
  class TEXT, risk REAL,
  scores JSONB,
  ride_id UUID REFERENCES rides(ride_id),
  frame_id TEXT REFERENCES frames(frame_id),
  embed_id TEXT
);

CREATE TABLE IF NOT EXISTS embeds (
  embed_id TEXT PRIMARY KEY,
  hazard_id UUID REFERENCES hazards(hazard_id),
  vec VECTOR(512)
);

CREATE TABLE IF NOT EXISTS hazard_clusters (
  cluster_id BIGSERIAL PRIMARY KEY,
  class TEXT,
  centroid GEOGRAPHY(POINT),
  count INT,
  bbox GEOGRAPHY(POLYGON),
  last_ts TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS frames_geom_idx ON frames USING GIST(geom);
CREATE INDEX IF NOT EXISTS hazards_geom_idx ON hazards USING GIST(geom);
CREATE INDEX IF NOT EXISTS hazard_clusters_centroid_idx ON hazard_clusters USING GIST(centroid);
CREATE INDEX IF NOT EXISTS hazards_class_ts ON hazards(class, ts DESC);
CREATE INDEX IF NOT EXISTS embeds_vec_idx ON embeds USING ivfflat (vec vector_cosine_ops) WITH (lists = 100);
