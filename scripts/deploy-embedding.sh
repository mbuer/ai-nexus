#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd systemctl
ensure_not_root

"$REPO_ROOT/scripts/build-embedding.sh"
"$REPO_ROOT/scripts/migrate.sh"

podman network inspect ai-nexus-internal >/dev/null 2>&1 || {
    echo "ERROR: ai-nexus-internal does not exist." >&2
    exit 1
}

podman network inspect ai-nexus-internal | grep -q '"internal": true' || {
    echo "ERROR: ai-nexus-internal is not internal." >&2
    exit 1
}

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$REPO_ROOT/containers/ai-nexus-embedding.container"     "$HOME/.config/containers/systemd/ai-nexus-embedding.container"

systemctl --user daemon-reload
systemctl --user restart ai-nexus-embedding.service

"$REPO_ROOT/scripts/verify-embedding.sh"
