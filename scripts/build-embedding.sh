#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

BASE_TAG="docker.io/library/python:3.12-slim"
IMAGE="localhost/ai-nexus-embedding:1"
MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION="1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

echo "Pulling base image..."
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
echo "Pinned model revision: $MODEL_REVISION"

podman build     --pull=never     --build-arg BASE_IMAGE="$pinned_base"     --build-arg MODEL_NAME="$MODEL_NAME"     --build-arg MODEL_REVISION="$MODEL_REVISION"     -t "$IMAGE"     "$REPO_ROOT/services/embedding"

echo "Embedding image built: $IMAGE"
