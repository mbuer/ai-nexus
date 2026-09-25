#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd sha256sum
wait_for_postgres

umask 077
mkdir -p "$AI_NEXUS_BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dump="$AI_NEXUS_BACKUP_DIR/birdynator-$stamp.dump"
globals="$AI_NEXUS_BACKUP_DIR/globals-$stamp.sql"

podman exec ai-nexus-postgres pg_dump -U postgres -Fc -d birdynator > "$dump"
podman exec ai-nexus-postgres pg_dumpall -U postgres --globals-only > "$globals"
chmod 600 "$dump" "$globals"
sha256sum "$dump" "$globals" > "$AI_NEXUS_BACKUP_DIR/SHA256SUMS-$stamp"
find "$AI_NEXUS_BACKUP_DIR" -type f -mtime +"$AI_NEXUS_BACKUP_RETENTION_DAYS" -delete

echo "Backup created: $dump"
if [[ "$AI_NEXUS_BACKUP_DIR" == "$HOME/"* ]]; then
    echo "NOTE: this backup is still on the VM. Override AI_NEXUS_BACKUP_DIR with an off-VM mount for stronger recovery."
fi
