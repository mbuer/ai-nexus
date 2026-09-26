#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
for cmd in podman systemctl sudo sed grep loginctl; do require_cmd "$cmd"; done
ensure_not_root

echo "== AI Nexus PostgreSQL/runtime foundation bootstrap =="

mkdir -p "$AI_NEXUS_RUNTIME_ROOT"/{agents,services,data,secrets} "$AI_NEXUS_BACKUP_DIR"
chmod 700 "$AI_NEXUS_RUNTIME_ROOT/secrets"

for name in postgres-superuser-password birdynator-db-password; do
    file="$AI_NEXUS_RUNTIME_ROOT/secrets/$name"
    [[ -f "$file" ]] || { echo "ERROR: missing secret file: $file" >&2; exit 1; }
    chmod 600 "$file"
    podman secret inspect "$name" >/dev/null 2>&1 || podman secret create "$name" "$file" >/dev/null
done

podman network inspect ai-nexus-internal >/dev/null 2>&1 || podman network create --internal ai-nexus-internal >/dev/null
podman network inspect ai-nexus-internal | grep -q '"internal": true' || { echo "ERROR: ai-nexus-internal is not internal." >&2; exit 1; }
podman volume inspect ai-nexus-postgres-data >/dev/null 2>&1 || podman volume create ai-nexus-postgres-data >/dev/null

echo "Resolving PostgreSQL image digest..."
podman pull "$POSTGRES_IMAGE_TAG" >/dev/null
digest="$(podman image inspect "$POSTGRES_IMAGE_TAG" --format '{{.Digest}}')"
[[ -n "$digest" && "$digest" != "<none>" ]] || { echo "ERROR: image digest unavailable." >&2; exit 1; }
image_repo="${POSTGRES_IMAGE_TAG%%:*}"
pinned_image="$image_repo@$digest"
echo "Pinned image: $pinned_image"

if podman container inspect ai-nexus-postgres >/dev/null 2>&1; then
    podman ps --format '{{.Names}}' | grep -qx ai-nexus-postgres || podman start ai-nexus-postgres >/dev/null
else
    podman run -d --name ai-nexus-postgres --network ai-nexus-internal       --secret postgres-superuser-password,type=mount,target=postgres-password       -e POSTGRES_USER=postgres -e POSTGRES_DB=postgres       -e POSTGRES_PASSWORD_FILE=/run/secrets/postgres-password       -v ai-nexus-postgres-data:/var/lib/postgresql/data "$pinned_image" >/dev/null
fi

wait_for_postgres
"$REPO_ROOT/scripts/migrate.sh"
"$REPO_ROOT/scripts/backup-postgres.sh"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
sed "s|@@POSTGRES_IMAGE@@|$pinned_image|g" "$REPO_ROOT/containers/ai-nexus-postgres.container.in" > "$tmp/ai-nexus-postgres.container"

if [[ -x /usr/lib/systemd/system-generators/podman-system-generator ]]; then
    QUADLET_UNIT_DIRS="$tmp" /usr/lib/systemd/system-generators/podman-system-generator --user --dryrun >/dev/null
fi

mkdir -p "$HOME/.config/containers/systemd"
install -m 600 "$tmp/ai-nexus-postgres.container" "$HOME/.config/containers/systemd/ai-nexus-postgres.container"

echo "Switching PostgreSQL to rootless Quadlet lifecycle..."
podman stop ai-nexus-postgres >/dev/null
podman rm ai-nexus-postgres >/dev/null

[[ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null || true)" == "yes" ]] || sudo loginctl enable-linger "$USER"
systemctl --user daemon-reload
systemctl --user start ai-nexus-postgres.service
wait_for_postgres
"$REPO_ROOT/scripts/verify.sh"

echo "Foundation bootstrap complete. Next: make verify && make restore-test"
