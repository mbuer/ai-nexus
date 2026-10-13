-- Prepared feedback store. Apply only after explicit migration/privilege approval.
-- The scheduled agent receives no new rights. Reviewer identity is curated by an operator.
SET ROLE birdynator_owner;

CREATE TABLE public.journal_reviewers (
    reviewer_id UUID PRIMARY KEY,
    label TEXT CHECK (length(label) <= 80),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE public.journal_feedback (
    feedback_id UUID PRIMARY KEY,
    reviewer_id UUID NOT NULL REFERENCES public.journal_reviewers(reviewer_id),
    analysis_id BIGINT NOT NULL REFERENCES public.analysis_runs(id) ON DELETE RESTRICT,
    supersedes UUID UNIQUE REFERENCES public.journal_feedback(feedback_id) ON DELETE RESTRICT,
    client_created_at TIMESTAMPTZ NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload_sha256 TEXT NOT NULL CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    document JSONB NOT NULL CHECK (jsonb_typeof(document) = 'object'),
    CHECK (supersedes IS NULL OR supersedes <> feedback_id)
);
CREATE INDEX journal_feedback_analysis ON public.journal_feedback(analysis_id, imported_at);
CREATE INDEX journal_feedback_reviewer ON public.journal_feedback(reviewer_id, imported_at);

CREATE FUNCTION public.import_journal_feedback(raw_document TEXT)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    doc JSONB;
    target JSONB;
    identifier UUID;
    reviewer UUID;
    prior UUID;
    existing public.journal_feedback%ROWTYPE;
    predecessor public.journal_feedback%ROWTYPE;
    source public.analysis_runs%ROWTYPE;
    stored public.journal_feedback%ROWTYPE;
BEGIN
    IF octet_length(raw_document) > 32768 THEN
        RAISE EXCEPTION 'Feedback exceeds size limit';
    END IF;
    doc := raw_document::JSONB;
    IF jsonb_typeof(doc) IS DISTINCT FROM 'object' OR doc->>'schema_version' IS DISTINCT FROM 'journal-feedback-v1'
       OR (SELECT count(*) FROM jsonb_object_keys(doc)) <> 11
       OR NOT doc ?& ARRAY['schema_version','feedback_id','reviewer_id','created_at','supersedes','target',
                           'overall','issue_tags','comment','wanted_instead','sections'] THEN
        RAISE EXCEPTION 'Unexpected feedback format';
    END IF;
    identifier := (doc->>'feedback_id')::UUID;
    reviewer := (doc->>'reviewer_id')::UUID;
    prior := (doc->>'supersedes')::UUID;
    target := doc->'target';
    IF identifier IS NULL OR reviewer IS NULL OR jsonb_typeof(target) <> 'object' THEN
        RAISE EXCEPTION 'Missing feedback identity';
    END IF;
    -- Serializes imports of the same ID; duplicate delivery is ordinary, not an update.
    PERFORM pg_advisory_xact_lock(hashtextextended(identifier::TEXT, 0));
    SELECT * INTO existing FROM public.journal_feedback WHERE feedback_id = identifier;
    IF FOUND THEN
        IF existing.document <> doc THEN
            RAISE EXCEPTION 'Feedback UUID collision with different content';
        END IF;
        RETURN jsonb_build_object('feedback_id', identifier, 'payload_sha256', existing.payload_sha256,
                                  'status', 'already_imported', 'imported_at', existing.imported_at);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.journal_reviewers WHERE reviewer_id = reviewer AND active) THEN
        RAISE EXCEPTION 'Reviewer is not accepted for import';
    END IF;
    SELECT * INTO source FROM public.analysis_runs WHERE id = (target->>'analysis_id')::BIGINT;
    IF NOT FOUND OR source.analysis_type <> 'birdnet_recent_vs_baseline'
       OR source.model IS DISTINCT FROM target->>'model'
       OR source.parameters->>'prompt_version' IS DISTINCT FROM target->>'prompt_version'
       OR source.source_digest IS DISTINCT FROM target->>'source_digest'
       OR to_char(source.source_latest_hour, 'YYYY-MM-DD"T"HH24:MI:SS') IS DISTINCT FROM target->>'source_latest_hour'
       OR encode(sha256(convert_to(source.result_text, 'UTF8')), 'hex') IS DISTINCT FROM target->>'narrative_digest' THEN
        RAISE EXCEPTION 'Feedback target differs from saved analysis';
    END IF;
    IF prior IS NOT NULL THEN
        SELECT * INTO predecessor FROM public.journal_feedback WHERE feedback_id = prior FOR UPDATE;
        IF NOT FOUND OR predecessor.reviewer_id <> reviewer OR predecessor.document->'target' <> target
           OR EXISTS (SELECT 1 FROM public.journal_feedback WHERE supersedes = prior) THEN
            RAISE EXCEPTION 'Superseded review differs or already has a successor';
        END IF;
    END IF;
    INSERT INTO public.journal_feedback(feedback_id, reviewer_id, analysis_id, supersedes,
                                       client_created_at, payload_sha256, document)
    VALUES (identifier, reviewer, source.id, prior, (doc->>'created_at')::TIMESTAMPTZ,
            encode(sha256(convert_to(raw_document, 'UTF8')), 'hex'), doc)
    RETURNING * INTO stored;
    RETURN jsonb_build_object('feedback_id', identifier, 'payload_sha256', stored.payload_sha256,
                              'status', 'imported', 'imported_at', stored.imported_at);
END;
$$;
REVOKE ALL ON TABLE public.journal_reviewers, public.journal_feedback FROM PUBLIC;
REVOKE ALL ON FUNCTION public.import_journal_feedback(TEXT) FROM PUBLIC;
RESET ROLE;

CREATE ROLE journal_feedback_importer NOLOGIN;
GRANT USAGE ON SCHEMA public TO journal_feedback_importer;
GRANT EXECUTE ON FUNCTION public.import_journal_feedback(TEXT) TO journal_feedback_importer;
-- No table writes, no canonical memory rights, no agent grants and no password.
-- An explicitly authorized administrative import session SET ROLEs to this role.
