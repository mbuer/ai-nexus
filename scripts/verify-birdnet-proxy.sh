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

security_state="$(podman exec ai-nexus-birdnet-proxy sh -c     'grep -E "^(CapPrm|CapEff|CapBnd|NoNewPrivs|Seccomp):" /proc/1/status')"

[[ "$security_state" == *'CapPrm:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: BirdNET proxy has permitted Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapEff:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: BirdNET proxy has effective Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapBnd:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: BirdNET proxy capability bounding set is not empty: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'NoNewPrivs:'$'\t''1'* ]] || {
    echo "ERROR: BirdNET proxy no-new-privileges is not active: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'Seccomp:'$'\t''2'* ]] || {
    echo "ERROR: BirdNET proxy seccomp filtering is not active: $security_state" >&2
    exit 1
}

ipc_mode="$(podman inspect ai-nexus-birdnet-proxy --format '{{.HostConfig.IpcMode}}')"
[[ "$ipc_mode" == "private" ]] || {
    echo "ERROR: BirdNET proxy IPC namespace is not private: $ipc_mode" >&2
    exit 1
}

echo "✓ BirdNET proxy reaches its fixed PostgreSQL destination"
echo "✓ BirdNET proxy is not attached to the agent-memory service network"
echo "✓ no host port published"
echo "✓ Linux capabilities dropped"
echo "✓ no-new-privileges active"
echo "✓ seccomp filtering active"
echo "✓ IPC namespace private"
