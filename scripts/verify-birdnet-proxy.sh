#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

: "${BIRDNET_SOURCE_HOST:?Set BIRDNET_SOURCE_HOST in config/runtime.local.env}"

for _ in $(seq 1 20); do
    if podman exec -i ai-nexus-birdnet-proxy python - <<'PY' >/dev/null 2>&1
import os, socket
socket.create_connection((os.environ["BIRDNET_SOURCE_HOST"], 5432), timeout=3).close()
PY
    then
        break
    fi
    sleep 1
done

podman exec -i ai-nexus-birdnet-proxy python - <<'PY'
import os, socket
socket.create_connection((os.environ["BIRDNET_SOURCE_HOST"], 5432), timeout=5).close()
print("birdnet-db-egress-ok")
PY

if podman exec -i ai-nexus-birdnet-proxy python - <<'PY' >/dev/null 2>&1
import socket
socket.gethostbyname("ai-nexus-postgres")
PY
then
    echo "ERROR: BirdNET proxy can resolve the agent-memory PostgreSQL service." >&2
    exit 1
fi

[[ -z "$(podman port ai-nexus-birdnet-proxy 2>/dev/null)" ]] || {
    echo "ERROR: BirdNET proxy unexpectedly publishes a host port." >&2
    exit 1
}

echo "✓ BirdNET proxy reaches its fixed PostgreSQL destination"
echo "✓ BirdNET proxy is not attached to the agent-memory service network"
echo "✓ no host port published"
