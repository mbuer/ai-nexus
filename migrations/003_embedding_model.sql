SET ROLE birdynator_owner;

INSERT INTO embedding_models (slug, provider, model_name, model_revision, dimensions, active)
VALUES (
    'all-minilm-l6-v2-1110a24',
    'huggingface',
    'sentence-transformers/all-MiniLM-L6-v2',
    '1110a243fdf4706b3f48f1d95db1a4f5529b4d41',
    384,
    TRUE
)
ON CONFLICT (provider, model_name, model_revision)
DO UPDATE SET dimensions = EXCLUDED.dimensions, active = TRUE;

RESET ROLE;
