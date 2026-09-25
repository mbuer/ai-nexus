#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_runtime_config() {
    source "$REPO_ROOT/config/runtime.example.env"
    if [[ -f "$REPO_ROOT/config/runtime.local.env" ]]; then
        source "$REPO_ROOT/config/runtime.local.env"
    fi
    AI_NEXUS_RUNTIME_ROOT="${AI_NEXUS_RUNTIME_ROOT/#\$HOME/$HOME}"
    AI_NEXUS_BACKUP_DIR="${AI_NEXUS_BACKUP_DIR/#\$HOME/$HOME}"
    export AI_NEXUS_RUNTIME_ROOT AI_NEXUS_BACKUP_DIR AI_NEXUS_BACKUP_RETENTION_DAYS POSTGRES_IMAGE_TAG
}
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: missing command: $1" >&2; exit 1; }; }
ensure_not_root() { [[ "$(id -u)" -ne 0 ]] || { echo "ERROR: run as the normal rootless Podman user." >&2; exit 1; }; }
postgres_ready() { podman exec ai-nexus-postgres pg_isready -U postgres -d postgres >/dev/null 2>&1; }
wait_for_postgres() {
    local tries=30
    until postgres_ready; do
        ((tries--)) || { echo "ERROR: PostgreSQL did not become ready." >&2; podman logs --tail 80 ai-nexus-postgres >&2 || true; exit 1; }
        sleep 1
    done
}
