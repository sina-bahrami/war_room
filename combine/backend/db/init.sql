CREATE EXTENSION IF NOT EXISTS pgcrypto;

DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS timescaledb;
EXCEPTION
  WHEN undefined_file THEN
    RAISE NOTICE 'timescaledb extension not available in this image; continuing without hypertables';
END
$$;

CREATE TABLE IF NOT EXISTS source_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  status TEXT NOT NULL,
  records_seen INTEGER NOT NULL DEFAULT 0,
  records_upserted INTEGER NOT NULL DEFAULT 0,
  started_at TIMESTAMPTZ NOT NULL,
  finished_at TIMESTAMPTZ,
  message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_runs_source_started
  ON source_runs (source_id, started_at DESC);

CREATE TABLE IF NOT EXISTS tenders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id TEXT NOT NULL,
  source_name TEXT NOT NULL,
  external_id TEXT NOT NULL,
  title TEXT NOT NULL,
  buyer_name TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  procurement_stage TEXT NOT NULL,
  source_url TEXT NOT NULL,
  published_at TIMESTAMPTZ,
  closes_at TIMESTAMPTZ,
  estimated_value NUMERIC(18, 2),
  currency TEXT NOT NULL DEFAULT 'AUD',
  state TEXT NOT NULL DEFAULT 'National',
  region TEXT NOT NULL DEFAULT '',
  category TEXT NOT NULL DEFAULT 'General',
  tags TEXT[] NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active',
  priority_score NUMERIC(8, 2) NOT NULL DEFAULT 0,
  is_internal BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_tender_source_external UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_tenders_stage ON tenders (procurement_stage);
CREATE INDEX IF NOT EXISTS idx_tenders_source ON tenders (source_id);
CREATE INDEX IF NOT EXISTS idx_tenders_closes_at ON tenders (closes_at);
CREATE INDEX IF NOT EXISTS idx_tenders_state ON tenders (state);
CREATE INDEX IF NOT EXISTS idx_tenders_priority ON tenders (priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_tenders_search
  ON tenders USING GIN (to_tsvector('english', coalesce(title, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(buyer_name, '')));
