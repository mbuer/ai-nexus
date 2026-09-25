#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
load_runtime_config
require_cmd systemctl
ensure_not_root

bash "$REPO_ROOT/scripts/migrate.sh"
bash "$REPO_ROOT/scripts/build-birdynator.sh"

systemctl --user restart ai-nexus-birdynator.service

bash "$REPO_ROOT/scripts/verify-birdynator.sh"
