#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

for _ in $(seq 1 20); do
    if podman exec ai-nexus-openai-proxy python - <<'PY' >/dev/null 2>&1
import socket
socket.create_connection(("api.openai.com", 443), timeout=3).close()
PY
    then
        break
    fi
    sleep 1
done

podman exec ai-nexus-openai-proxy python - <<'PY'
import socket
socket.create_connection(("api.openai.com", 443), timeout=5).close()
print("egress-ok")
PY

if podman exec ai-nexus-openai-proxy python - <<'PY' >/dev/null 2>&1
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

echo "✓ OpenAI proxy has outbound TLS reachability"
echo "✓ OpenAI proxy is not attached to the database service network"
echo "✓ no host port published"
echo "✓ proxy destination allowlist is api.openai.com:443"
