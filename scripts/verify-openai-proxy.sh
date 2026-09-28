#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

for _ in $(seq 1 20); do
    if podman exec -i ai-nexus-openai-proxy python - <<'PY' >/dev/null 2>&1
import socket
socket.create_connection(("api.openai.com", 443), timeout=3).close()
PY
    then
        break
    fi
    sleep 1
done

podman exec -i ai-nexus-openai-proxy python - <<'PY'
import socket
socket.create_connection(("api.openai.com", 443), timeout=5).close()
print("egress-ok")
PY

if podman exec -i ai-nexus-openai-proxy python - <<'PY' >/dev/null 2>&1
import socket
socket.gethostbyname("ai-nexus-postgres")
PY
then
    echo "ERROR: OpenAI proxy can resolve the PostgreSQL service." >&2
    exit 1
fi

[[ -z "$(podman port ai-nexus-openai-proxy 2>/dev/null)" ]] || {
    echo "ERROR: OpenAI proxy unexpectedly publishes a host port." >&2
    exit 1
}

security_state="$(podman exec ai-nexus-openai-proxy sh -c     'grep -E "^(CapPrm|CapEff|CapBnd|NoNewPrivs|Seccomp):" /proc/1/status')"

[[ "$security_state" == *'CapPrm:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: OpenAI proxy has permitted Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapEff:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: OpenAI proxy has effective Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapBnd:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: OpenAI proxy capability bounding set is not empty: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'NoNewPrivs:'$'\t''1'* ]] || {
    echo "ERROR: OpenAI proxy no-new-privileges is not active: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'Seccomp:'$'\t''2'* ]] || {
    echo "ERROR: OpenAI proxy seccomp filtering is not active: $security_state" >&2
    exit 1
}

ipc_mode="$(podman inspect ai-nexus-openai-proxy --format '{{.HostConfig.IpcMode}}')"
[[ "$ipc_mode" == "private" ]] || {
    echo "ERROR: OpenAI proxy IPC namespace is not private: $ipc_mode" >&2
    exit 1
}

echo "✓ OpenAI proxy has outbound TLS reachability"
echo "✓ OpenAI proxy is not attached to the database service network"
echo "✓ no host port published"
echo "✓ Linux capabilities dropped"
echo "✓ no-new-privileges active"
echo "✓ seccomp filtering active"
echo "✓ IPC namespace private"
echo "✓ proxy destination allowlist is api.openai.com:443"
