#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd systemctl
ensure_not_root

bash "$REPO_ROOT/scripts/build-openai-proxy.sh"

podman network inspect ai-nexus-proxy-link >/dev/null 2>&1 ||     podman network create --internal ai-nexus-proxy-link >/dev/null

podman network inspect ai-nexus-proxy-link | grep -q '"internal": true' || {
    echo "ERROR: ai-nexus-proxy-link must be internal." >&2
    exit 1
}

podman network inspect ai-nexus-egress >/dev/null 2>&1 ||     podman network create ai-nexus-egress >/dev/null

if podman network inspect ai-nexus-egress | grep -q '"internal": true'; then
    echo "ERROR: ai-nexus-egress must permit outbound connectivity." >&2
    exit 1
fi

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$REPO_ROOT/containers/ai-nexus-openai-proxy.container"     "$HOME/.config/containers/systemd/ai-nexus-openai-proxy.container"

systemctl --user daemon-reload
systemctl --user restart ai-nexus-openai-proxy.service

bash "$REPO_ROOT/scripts/verify-openai-proxy.sh"
