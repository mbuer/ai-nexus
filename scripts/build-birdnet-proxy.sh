#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

BASE_TAG="docker.io/library/python:3.12-slim"
IMAGE="localhost/ai-nexus-birdnet-proxy:1"

podman pull "$BASE_TAG" >/dev/null
digest="$(podman image inspect "$BASE_TAG" --format '{{.Digest}}')"
[[ -n "$digest" && "$digest" != "<none>" ]] || {
    echo "ERROR: could not resolve Python base-image digest." >&2
    exit 1
}
base_repo="${BASE_TAG%%:*}"
pinned_base="$base_repo@$digest"

echo "Building $IMAGE"
echo "Pinned base: $pinned_base"

podman build     --pull=never     --build-arg BASE_IMAGE="$pinned_base"     -t "$IMAGE"     "$REPO_ROOT/services/birdnet-proxy"

echo "BirdNET proxy image built: $IMAGE"
