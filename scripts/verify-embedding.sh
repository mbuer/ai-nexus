#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
ensure_not_root

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

for _ in $(seq 1 60); do
    if podman exec -i ai-nexus-embedding python - <<'PY' >"$tmp" 2>/dev/null
from urllib.request import urlopen
with urlopen("http://127.0.0.1:8000/health", timeout=2) as r:
    print(r.read().decode())
PY
    then
        break
    fi
    sleep 1
done

health="$(cat "$tmp")"
[[ "$health" == *'"status":"ok"'* ]] || {
    echo "ERROR: embedding health check failed: $health" >&2
    podman logs --tail 100 ai-nexus-embedding >&2 || true
    exit 1
}

[[ "$health" == *'"dimensions":384'* ]] || {
    echo "ERROR: embedding service did not report 384 dimensions." >&2
    exit 1
}

[[ -z "$(podman port ai-nexus-embedding 2>/dev/null)" ]] || {
    echo "ERROR: embedding service unexpectedly publishes a host port." >&2
    exit 1
}

security_state="$(podman exec ai-nexus-embedding sh -c     'grep -E "^(CapPrm|CapEff|CapBnd|NoNewPrivs|Seccomp):" /proc/1/status')"

[[ "$security_state" == *'CapPrm:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: embedding service has permitted Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapEff:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: embedding service has effective Linux capabilities: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'CapBnd:'$'\t''0000000000000000'* ]] || {
    echo "ERROR: embedding service capability bounding set is not empty: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'NoNewPrivs:'$'\t''1'* ]] || {
    echo "ERROR: embedding service no-new-privileges is not active: $security_state" >&2
    exit 1
}

[[ "$security_state" == *'Seccomp:'$'\t''2'* ]] || {
    echo "ERROR: embedding service seccomp filtering is not active: $security_state" >&2
    exit 1
}

ipc_mode="$(podman inspect ai-nexus-embedding --format '{{.HostConfig.IpcMode}}')"
[[ "$ipc_mode" == "private" ]] || {
    echo "ERROR: embedding service IPC namespace is not private: $ipc_mode" >&2
    exit 1
}

result="$(podman exec -i ai-nexus-embedding python - <<'PY'
import json
from urllib.request import Request, urlopen
payload = json.dumps({"texts": ["A Western Tanager appeared after rain."]}).encode()
req = Request("http://127.0.0.1:8000/embed", data=payload, headers={"Content-Type":"application/json"})
with urlopen(req, timeout=15) as r:
    data = json.loads(r.read())
print(data["dimensions"], len(data["embeddings"]), len(data["embeddings"][0]))
PY
)"

[[ "$result" == "384 1 384" ]] || {
    echo "ERROR: embedding smoke test failed: $result" >&2
    exit 1
}

echo "✓ embedding service healthy"
echo "✓ pinned 384-dimensional model loaded"
echo "✓ no host port published"
echo "✓ Linux capabilities dropped"
echo "✓ no-new-privileges active"
echo "✓ seccomp filtering active"
echo "✓ IPC namespace private"
echo "✓ text -> vector smoke test passed"
