-- Canonical memory is model-independent; embeddings are versioned separately.
SET ROLE birdynator_owner;

ALTER TABLE memory
    ADD COLUMN IF NOT EXISTS source_type TEXT NOT NULL DEFAULT 'manual',
    ADD COLUMN IF NOT EXISTS source_ref TEXT,
    ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS confidence NUMERIC(4,3),
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active',
    ADD COLUMN IF NOT EXISTS supersedes_id BIGINT REFERENCES memory(id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'memory_confidence_range') THEN
        ALTER TABLE memory ADD CONSTRAINT memory_confidence_range
            CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'memory_status_allowed') THEN
        ALTER TABLE memory ADD CONSTRAINT memory_status_allowed
            CHECK (status IN ('active', 'superseded', 'retracted'));
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS embedding_models (
    id BIGSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_revision TEXT NOT NULL,
    dimensions INTEGER NOT NULL CHECK (dimensions > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provider, model_name, model_revision)
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id BIGSERIAL PRIMARY KEY,
    memory_id BIGINT NOT NULL REFERENCES memory(id) ON DELETE CASCADE,
    model_id BIGINT NOT NULL REFERENCES embedding_models(id) ON DELETE RESTRICT,
    embedding vector NOT NULL,
    dimensions INTEGER GENERATED ALWAYS AS (vector_dims(embedding)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (memory_id, model_id)
);

CREATE INDEX IF NOT EXISTS idx_memory_status ON memory(status);
CREATE INDEX IF NOT EXISTS idx_memory_observed_at ON memory(observed_at);
CREATE INDEX IF NOT EXISTS idx_memory_embeddings_model ON memory_embeddings(model_id);

DO $$
DECLARE
    has_embedding_column BOOLEAN;
    has_embedding_data BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name='memory' AND column_name='embedding'
    ) INTO has_embedding_column;

    IF has_embedding_column THEN
        EXECUTE 'SELECT EXISTS (SELECT 1 FROM memory WHERE embedding IS NOT NULL)'
            INTO has_embedding_data;
        IF has_embedding_data THEN
            RAISE EXCEPTION 'memory.embedding contains data; migrate it before dropping the prototype column';
        END IF;
        EXECUTE 'DROP INDEX IF EXISTS idx_memory_embedding';
        EXECUTE 'ALTER TABLE memory DROP COLUMN embedding';
    END IF;
END
$$;

RESET ROLE;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE memory TO birdynator;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE memory_embeddings TO birdynator;
GRANT SELECT ON TABLE embedding_models TO birdynator;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO birdynator;

ALTER DEFAULT PRIVILEGES FOR ROLE birdynator_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO birdynator;
ALTER DEFAULT PRIVILEGES FOR ROLE birdynator_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO birdynator;
