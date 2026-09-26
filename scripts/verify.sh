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

postgres_uid="$(podman exec ai-nexus-postgres sh -c "awk '/^Uid:/{print \$2}' /proc/1/status")"
postgres_gid="$(podman exec ai-nexus-postgres sh -c "awk '/^Gid:/{print \$2}' /proc/1/status")"
[[ "$postgres_uid" == "999" && "$postgres_gid" == "999" ]] && ok "PostgreSQL server runs as UID/GID 999" || bad "unexpected PostgreSQL process identity: $postgres_uid:$postgres_gid"

security_state="$(podman exec ai-nexus-postgres sh -c 'grep -E "^(NoNewPrivs|Seccomp):" /proc/1/status')"
[[ "$security_state" == *'NoNewPrivs:'"$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='birdynator';")"
[[ "$owner" == "birdynator_owner" ]] && ok "database owned by non-login owner role" || bad "unexpected database owner: $owner"

attrs="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT rolsuper||':'||rolcreaterole||':'||rolcreatedb||':'||rolcanlogin FROM pg_roles WHERE rolname='birdynator';")"
[[ "$attrs" == "false:false:false:true" || "$attrs" == "f:f:f:t" ]] && ok "Birdynator runtime role has no admin attributes" || bad "unexpected Birdynator role attributes: $attrs"

mem_owner="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='memory';")"
[[ "$mem_owner" == "birdynator_owner" ]] && ok "memory table not owned by runtime role" || bad "unexpected memory owner: $mem_owner"

podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT to_regclass('public.memory_embeddings');" | grep -qx memory_embeddings     && ok "model-aware memory_embeddings table exists" || bad "memory_embeddings table missing"

old="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='memory' AND column_name='embedding');")"
[[ "$old" == "f" ]] && ok "fixed-dimension prototype embedding column removed" || bad "prototype embedding column still exists"

if git -C "$REPO_ROOT" ls-files | grep -Eq '(^|/)(secrets|credentials)/|runtime\.local\.env$|\.key$|\.pem$|\.secret$'; then bad "Git tracks a secret-like path"; else ok "Git secret-pattern check passed"; fi

if ((fail)); then echo "Verification failed." >&2; exit 1; fi
echo "AI Nexus verification passed."
\t''1'* ]] && ok "PostgreSQL no-new-privileges active" || bad "PostgreSQL no-new-privileges not active"
[[ "$security_state" == *'Seccomp:'"$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='birdynator';")"
[[ "$owner" == "birdynator_owner" ]] && ok "database owned by non-login owner role" || bad "unexpected database owner: $owner"

attrs="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT rolsuper||':'||rolcreaterole||':'||rolcreatedb||':'||rolcanlogin FROM pg_roles WHERE rolname='birdynator';")"
[[ "$attrs" == "false:false:false:true" || "$attrs" == "f:f:f:t" ]] && ok "Birdynator runtime role has no admin attributes" || bad "unexpected Birdynator role attributes: $attrs"

mem_owner="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='memory';")"
[[ "$mem_owner" == "birdynator_owner" ]] && ok "memory table not owned by runtime role" || bad "unexpected memory owner: $mem_owner"

podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT to_regclass('public.memory_embeddings');" | grep -qx memory_embeddings     && ok "model-aware memory_embeddings table exists" || bad "memory_embeddings table missing"

old="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='memory' AND column_name='embedding');")"
[[ "$old" == "f" ]] && ok "fixed-dimension prototype embedding column removed" || bad "prototype embedding column still exists"

if git -C "$REPO_ROOT" ls-files | grep -Eq '(^|/)(secrets|credentials)/|runtime\.local\.env$|\.key$|\.pem$|\.secret$'; then bad "Git tracks a secret-like path"; else ok "Git secret-pattern check passed"; fi

if ((fail)); then echo "Verification failed." >&2; exit 1; fi
echo "AI Nexus verification passed."
\t''2'* ]] && ok "PostgreSQL seccomp filtering active" || bad "PostgreSQL seccomp filtering not active"

ipc_mode="$(podman inspect ai-nexus-postgres --format '{{.HostConfig.IpcMode}}')"
[[ "$ipc_mode" == "private" ]] && ok "PostgreSQL IPC namespace private" || bad "unexpected PostgreSQL IPC mode: $ipc_mode"

secret_state="$(podman exec ai-nexus-postgres sh -c 'stat -c "%a %u:%g" /run/secrets/postgres-password')"
[[ "$secret_state" == "400 0:0" ]] && ok "PostgreSQL password secret is root-only mode 0400" || bad "unexpected PostgreSQL secret permissions: $secret_state"

data_state="$(podman exec ai-nexus-postgres sh -c 'stat -c "%a %u:%g" /var/lib/postgresql/data')"
[[ "$data_state" == "700 999:999" ]] && ok "PostgreSQL data directory is 0700 and owned by UID/GID 999" || bad "unexpected PostgreSQL data directory permissions: $data_state"

owner="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='birdynator';")"
[[ "$owner" == "birdynator_owner" ]] && ok "database owned by non-login owner role" || bad "unexpected database owner: $owner"

attrs="$(podman exec ai-nexus-postgres psql -U postgres -d postgres -Atqc "SELECT rolsuper||':'||rolcreaterole||':'||rolcreatedb||':'||rolcanlogin FROM pg_roles WHERE rolname='birdynator';")"
[[ "$attrs" == "false:false:false:true" || "$attrs" == "f:f:f:t" ]] && ok "Birdynator runtime role has no admin attributes" || bad "unexpected Birdynator role attributes: $attrs"

mem_owner="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT tableowner FROM pg_tables WHERE schemaname='public' AND tablename='memory';")"
[[ "$mem_owner" == "birdynator_owner" ]] && ok "memory table not owned by runtime role" || bad "unexpected memory owner: $mem_owner"

podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT to_regclass('public.memory_embeddings');" | grep -qx memory_embeddings     && ok "model-aware memory_embeddings table exists" || bad "memory_embeddings table missing"

old="$(podman exec ai-nexus-postgres psql -U postgres -d birdynator -Atqc "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='memory' AND column_name='embedding');")"
[[ "$old" == "f" ]] && ok "fixed-dimension prototype embedding column removed" || bad "prototype embedding column still exists"

if git -C "$REPO_ROOT" ls-files | grep -Eq '(^|/)(secrets|credentials)/|runtime\.local\.env$|\.key$|\.pem$|\.secret$'; then bad "Git tracks a secret-like path"; else ok "Git secret-pattern check passed"; fi

if ((fail)); then echo "Verification failed." >&2; exit 1; fi
echo "AI Nexus verification passed."
