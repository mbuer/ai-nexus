#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
wait_for_postgres

podman exec -i ai-nexus-postgres psql -U postgres -d birdynator -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SQL

for migration in "$REPO_ROOT"/migrations/*.sql; do
    version="$(basename "$migration")"
    applied="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc       "SELECT EXISTS (SELECT 1 FROM public.schema_migrations WHERE version = '$version');")"
    if [[ "$applied" == "t" ]]; then
        echo "Migration already applied: $version"
        continue
    fi
    echo "Applying migration: $version"
    podman exec -i ai-nexus-postgres psql -U postgres -d birdynator         -v ON_ERROR_STOP=1 --single-transaction < "$migration"
    podman exec ai-nexus-postgres psql -U postgres -d birdynator -v ON_ERROR_STOP=1         -c "INSERT INTO public.schema_migrations(version) VALUES ('$version');"
done
