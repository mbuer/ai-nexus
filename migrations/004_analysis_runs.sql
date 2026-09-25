-- Persist Birdynator analytical outputs without copying authoritative BirdNET source rows.
SET ROLE birdynator_owner;

CREATE TABLE IF NOT EXISTS analysis_runs (
    id BIGSERIAL PRIMARY KEY,
    analysis_type TEXT NOT NULL,
    model TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    source_latest_hour TIMESTAMPTZ,
    recent_hours INTEGER NOT NULL CHECK (recent_hours > 0),
    baseline_days INTEGER NOT NULL CHECK (baseline_days > 0),
    source_digest TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    result_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
    ON analysis_runs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_type_created_at
    ON analysis_runs(analysis_type, created_at DESC);

RESET ROLE;

GRANT SELECT, INSERT ON TABLE analysis_runs TO birdynator;
GRANT USAGE, SELECT ON SEQUENCE analysis_runs_id_seq TO birdynator;
