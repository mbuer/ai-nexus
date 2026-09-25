#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
wait_for_postgres

latest="$(find "$AI_NEXUS_BACKUP_DIR" -maxdepth 1 -type f -name 'birdynator-*.dump' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
[[ -n "$latest" ]] || { echo "ERROR: no backup found in $AI_NEXUS_BACKUP_DIR" >&2; exit 1; }

test_db="birdynator_restore_test"
podman exec ai-nexus-postgres dropdb -U postgres --if-exists "$test_db"
podman exec ai-nexus-postgres createdb -U postgres -O birdynator_owner "$test_db"
cat "$latest" | podman exec -i ai-nexus-postgres     pg_restore -U postgres -d "$test_db" --no-owner --role=birdynator_owner
podman exec ai-nexus-postgres psql -U postgres -d "$test_db" -v ON_ERROR_STOP=1     -c "SELECT count(*) AS restored_memories FROM memory;"
podman exec ai-nexus-postgres psql -U postgres -d "$test_db" -v ON_ERROR_STOP=1     -c "SELECT to_regclass('public.memory_embeddings') AS memory_embeddings;"
podman exec ai-nexus-postgres dropdb -U postgres "$test_db"
echo "Restore test passed."
