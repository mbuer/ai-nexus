#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd systemctl
ensure_not_root

bash "$REPO_ROOT/scripts/build-birdynator.sh"
bash "$REPO_ROOT/scripts/migrate.sh"
bash "$REPO_ROOT/scripts/deploy-openai-proxy.sh"

podman network inspect ai-nexus-internal >/dev/null 2>&1 || {
    echo "ERROR: ai-nexus-internal does not exist." >&2
    exit 1
}

podman network inspect ai-nexus-internal | grep -q '"internal": true' || {
    echo "ERROR: ai-nexus-internal is not internal." >&2
    exit 1
}

podman secret inspect openai-api-key >/dev/null 2>&1 || {
    echo "ERROR: Podman secret openai-api-key is missing." >&2
    exit 1
}

podman secret inspect birdynator-db-password >/dev/null 2>&1 || {
    echo "ERROR: Podman secret birdynator-db-password is missing." >&2
    exit 1
}

systemctl --user is-active --quiet ai-nexus-postgres.service || {
    echo "ERROR: PostgreSQL service is not active." >&2
    exit 1
}

systemctl --user is-active --quiet ai-nexus-embedding.service || {
    echo "ERROR: embedding service is not active." >&2
    exit 1
}

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$REPO_ROOT/containers/ai-nexus-birdynator.container" \
    "$HOME/.config/containers/systemd/ai-nexus-birdynator.container"

systemctl --user daemon-reload
systemctl --user restart ai-nexus-birdynator.service

bash "$REPO_ROOT/scripts/verify-birdynator.sh"
