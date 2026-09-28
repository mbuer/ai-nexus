#!/usr/bin/env bash
set -euo pipefail
cat <<'EOF'
AI Nexus bootstrap plan

1. Validate rootless Podman and local secret files.
2. Verify/create the isolated internal network and PostgreSQL volume.
3. Resolve the PostgreSQL image tag to an immutable image digest.
4. Apply versioned migrations:
   - separate schema ownership from Birdynator's runtime login
   - add provenance/lifecycle fields
   - move embeddings to a model-aware table
5. Create a logical PostgreSQL backup.
6. Render and validate a rootless Quadlet with resource limits.
7. Replace the manually started PostgreSQL container with the Quadlet service.
8. Enable user lingering for boot-time rootless services.
9. Run verification.

The bootstrap aborts instead of dropping a populated prototype embedding column.
EOF
