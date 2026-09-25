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
echo "✓ text -> vector smoke test passed"
