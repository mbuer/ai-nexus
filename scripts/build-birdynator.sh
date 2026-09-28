#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

BASE_TAG="docker.io/library/python:3.12-slim"
IMAGE="localhost/ai-nexus-birdynator:1"

if ! podman image exists "$BASE_TAG"; then
    echo "Base image missing; pulling $BASE_TAG..."
    podman pull "$BASE_TAG" >/dev/null
elif [[ "${BIRDYNATOR_REFRESH_BASE:-0}" == "1" ]]; then
    echo "Refreshing base image $BASE_TAG..."
    podman pull "$BASE_TAG" >/dev/null
else
    echo "Using cached base image (set BIRDYNATOR_REFRESH_BASE=1 to refresh)."
fi

digest="$(podman image inspect "$BASE_TAG" --format '{{.Digest}}')"
[[ -n "$digest" && "$digest" != "<none>" ]] || {
    echo "ERROR: could not resolve Python base-image digest." >&2
    exit 1
}

base_repo="${BASE_TAG%%:*}"
pinned_base="$base_repo@$digest"

echo "Building $IMAGE"
echo "Pinned base: $pinned_base"

podman build \
    --pull=never \
    --build-arg BASE_IMAGE="$pinned_base" \
    -t "$IMAGE" \
    "$REPO_ROOT/services/birdynator"

echo "Birdynator image built: $IMAGE"
