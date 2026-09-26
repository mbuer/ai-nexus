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

security_state="$(podman exec agent-birdynator sh -c     'grep -E "^(CapPrm|CapEff|CapBnd|NoNewPrivs|Seccomp):" /proc/1/status')"

[[ "$security_state" == *'CapPrm:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: Birdynator has permitted Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapEff:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: Birdynator has effective Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapBnd:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: Birdynator capability bounding set is not empty: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'NoNewPrivs:'$'\t''1'* ]] || {
    echo "ERROR: Birdynator no-new-privileges is not active: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'Seccomp:'
echo "✓ Birdynator DB role verified"
echo "✓ local embedding service reachable"
echo "✓ no host port published"
echo "✓ Linux capabilities dropped"
echo "✓ no-new-privileges active"
echo "✓ seccomp filtering active"
echo "✓ IPC namespace private"
echo "✓ Birdynator secrets restricted to UID/GID 10001 with mode 0400"
echo "✓ agent remains on internal-only network"


api_health="$(podman exec agent-birdynator python /app/birdynator.py api-health)"
[[ "$api_health" == *'"status": "ok"'* ]] || {
    echo "ERROR: Birdynator OpenAI API health check failed: $api_health" >&2
    exit 1
}

if podman exec -i agent-birdynator python - <<'PY' >/dev/null 2>&1
import socket
socket.create_connection(("1.1.1.1", 443), timeout=3).close()
PY
then
    echo "ERROR: Birdynator has direct Internet egress; expected proxy-only access." >&2
    exit 1
fi

echo "✓ OpenAI API reachable through controlled proxy"
echo "✓ direct Internet egress blocked from Birdynator"


birdnet_health="$(podman exec agent-birdynator python /app/birdynator.py birdnet-health)"
[[ "$birdnet_health" == *'"status": "ok"'* ]] || {
    echo "ERROR: Birdynator BirdNET datasource health check failed: $birdnet_health" >&2
    exit 1
}
[[ "$birdnet_health" == *'"read_only": "on"'* ]] || {
    echo "ERROR: BirdNET datasource session is not read-only: $birdnet_health" >&2
    exit 1
}

echo "✓ BirdNET datasource reachable through isolated proxy"
echo "✓ BirdNET datasource session is read-only"


podman exec agent-birdynator python /app/birdynator.py analysis-history --limit 1 >/dev/null

echo "✓ persisted analysis schema reachable"
\t''2'* ]] || {
    echo "ERROR: Birdynator seccomp filtering is not active: $security_state" >&2
    exit 1
}

ipc_mode="$(podman inspect agent-birdynator --format '{{.HostConfig.IpcMode}}')"
[[ "$ipc_mode" == "private" ]] || {
    echo "ERROR: Birdynator IPC namespace is not private: $ipc_mode" >&2
    exit 1
}

secret_state="$(podman exec agent-birdynator sh -c     'stat -c "%a %u:%g %n" /run/secrets/db-password /run/secrets/openai-api-key /run/secrets/birdnet-db-password')"

while IFS= read -r line; do
    [[ "$line" == "400 10001:10001 "* ]] || {
        echo "ERROR: Birdynator secret ownership/mode is not 0400 10001:10001: $line" >&2
        exit 1
    }
done <<< "$secret_state"

echo "✓ Birdynator container healthy"
echo "✓ Birdynator DB role verified"
echo "✓ local embedding service reachable"
echo "✓ no host port published"
echo "✓ Linux capabilities dropped"
echo "✓ no-new-privileges active"
echo "✓ seccomp filtering active"
echo "✓ agent remains on internal-only network"


api_health="$(podman exec agent-birdynator python /app/birdynator.py api-health)"
[[ "$api_health" == *'"status": "ok"'* ]] || {
    echo "ERROR: Birdynator OpenAI API health check failed: $api_health" >&2
    exit 1
}

if podman exec -i agent-birdynator python - <<'PY' >/dev/null 2>&1
import socket
socket.create_connection(("1.1.1.1", 443), timeout=3).close()
PY
then
    echo "ERROR: Birdynator has direct Internet egress; expected proxy-only access." >&2
    exit 1
fi

echo "✓ OpenAI API reachable through controlled proxy"
echo "✓ direct Internet egress blocked from Birdynator"


birdnet_health="$(podman exec agent-birdynator python /app/birdynator.py birdnet-health)"
[[ "$birdnet_health" == *'"status": "ok"'* ]] || {
    echo "ERROR: Birdynator BirdNET datasource health check failed: $birdnet_health" >&2
    exit 1
}
[[ "$birdnet_health" == *'"read_only": "on"'* ]] || {
    echo "ERROR: BirdNET datasource session is not read-only: $birdnet_health" >&2
    exit 1
}

echo "✓ BirdNET datasource reachable through isolated proxy"
echo "✓ BirdNET datasource session is read-only"


podman exec agent-birdynator python /app/birdynator.py analysis-history --limit 1 >/dev/null

echo "✓ persisted analysis schema reachable"
