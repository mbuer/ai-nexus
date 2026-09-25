#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

for _ in $(seq 1 30); do
    if podman exec agent-birdynator python /app/birdynator.py health >"$tmp" 2>/dev/null; then
        break
    fi
    sleep 1
done

health="$(cat "$tmp")"

[[ "$health" == *'"status": "ok"'* ]] || {
    echo "ERROR: Birdynator health check failed: $health" >&2
    podman logs --tail 100 agent-birdynator >&2 || true
    exit 1
}

[[ "$health" == *'"database_user": "birdynator"'* ]] || {
    echo "ERROR: Birdynator is not using its least-privilege DB role." >&2
    exit 1
}

[[ "$health" == *'"embedding_dimensions": 384'* ]] || {
    echo "ERROR: Birdynator cannot reach the expected embedding service." >&2
    exit 1
}

[[ -z "$(podman port agent-birdynator 2>/dev/null)" ]] || {
    echo "ERROR: Birdynator unexpectedly publishes a host port." >&2
    exit 1
}

echo "✓ Birdynator container healthy"
echo "✓ Birdynator DB role verified"
echo "✓ local embedding service reachable"
echo "✓ no host port published"
echo "✓ agent remains on internal-only network"
