#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd systemctl
require_cmd sed
ensure_not_root

podman container inspect ai-nexus-postgres >/dev/null 2>&1 || {
    echo "ERROR: ai-nexus-postgres does not exist." >&2
    exit 1
}

current_image="$(podman inspect ai-nexus-postgres --format '{{.ImageName}}')"
[[ -n "$current_image" ]] || {
    echo "ERROR: could not determine the current PostgreSQL image." >&2
    exit 1
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed "s|@@POSTGRES_IMAGE@@|$current_image|g"     "$REPO_ROOT/containers/ai-nexus-postgres.container.in" > "$tmp"

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$tmp"     "$HOME/.config/containers/systemd/ai-nexus-postgres.container"

systemctl --user daemon-reload
systemctl --user restart ai-nexus-postgres.service
wait_for_postgres

"$REPO_ROOT/scripts/migrate.sh"
"$REPO_ROOT/scripts/verify.sh"
"$REPO_ROOT/scripts/backup-postgres.sh"

echo "PostgreSQL hardening deployment complete."
