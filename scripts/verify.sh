#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd podman
require_cmd git
ensure_not_root

fail=0
ok(){ printf '✓ %s\n' "$1"; }
bad(){ printf '✗ %s\n' "$1" >&2; fail=1; }

[[ "$(podman info --format '{{.Host.Security.Rootless}}')" == "true" ]] && ok "Podman is rootless" || bad "Podman is not rootless"
podman network inspect ai-nexus-internal 2>/dev/null | grep -q '"internal": true' && ok "internal network is isolated" || bad "internal network is not isolated"
podman ps --format '{{.Names}}' | grep -qx ai-nexus-postgres && ok "PostgreSQL is running" || bad "PostgreSQL is not running"
[[ -z "$(podman port ai-nexus-postgres 2>/dev/null)" ]] && ok "PostgreSQL publishes no host ports" || bad "PostgreSQL publishes a host port"

owner="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='birdynator';")"
[[ "$owner" == "birdynator_owner" ]] && ok "database owned by non-login owner role" || bad "unexpected database owner: $owner"

attrs="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT rolsuper||':'||rolcreaterole||':'||rolcreatedb||':'||rolcanlogin FROM pg_roles WHERE rolname='birdynator';")"
[[ "$attrs" == "f:f:f:t" ]] && ok "Birdynator runtime role has no admin attributes" || bad "unexpected Birdynator role attributes: $attrs"

mem_owner="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='memory';")"
[[ "$mem_owner" == "birdynator_owner" ]] && ok "memory table not owned by runtime role" || bad "unexpected memory owner: $mem_owner"

podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT to_regclass('public.memory_embeddings');" | grep -qx memory_embeddings     && ok "model-aware memory_embeddings table exists" || bad "memory_embeddings table missing"

old="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='memory' AND column_name='embedding');")"
[[ "$old" == "f" ]] && ok "fixed-dimension prototype embedding column removed" || bad "prototype embedding column still exists"

if git -C "$REPO_ROOT" ls-files | grep -Eq '(^|/)(secrets|credentials)/|runtime\.local\.env$|\.key$|\.pem$|\.secret$'; then bad "Git tracks a secret-like path"; else ok "Git secret-pattern check passed"; fi

if ((fail)); then echo "Verification failed." >&2; exit 1; fi
echo "AI Nexus verification passed."
