#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd systemctl
require_cmd sed
ensure_not_root

: "${BIRDNET_SOURCE_HOST:?Set BIRDNET_SOURCE_HOST in config/runtime.local.env}"

case "$BIRDNET_SOURCE_HOST" in
    BIRDNET_DB_HOST|CHANGE_ME|"")
        echo "ERROR: set the real BirdNET PostgreSQL host only in config/runtime.local.env." >&2
        exit 1
        ;;
esac

bash "$REPO_ROOT/scripts/build-birdnet-proxy.sh"

podman network inspect ai-nexus-birdnet-link >/dev/null 2>&1 ||     podman network create --internal ai-nexus-birdnet-link >/dev/null

podman network inspect ai-nexus-birdnet-link | grep -q '"internal": true' || {
    echo "ERROR: ai-nexus-birdnet-link must be internal." >&2
    exit 1
}

podman network inspect ai-nexus-birdnet-egress >/dev/null 2>&1 ||     podman network create ai-nexus-birdnet-egress >/dev/null

if podman network inspect ai-nexus-birdnet-egress | grep -q '"internal": true'; then
    echo "ERROR: ai-nexus-birdnet-egress must permit routed access to the datasource." >&2
    exit 1
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
sed "s|@@BIRDNET_SOURCE_HOST@@|$BIRDNET_SOURCE_HOST|g"     "$REPO_ROOT/containers/ai-nexus-birdnet-proxy.container.in" > "$tmp"

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$tmp"     "$HOME/.config/containers/systemd/ai-nexus-birdnet-proxy.container"

systemctl --user daemon-reload
systemctl --user restart ai-nexus-birdnet-proxy.service

bash "$REPO_ROOT/scripts/verify-birdnet-proxy.sh"
