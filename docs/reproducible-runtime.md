# Reproducible Runtime

AI Nexus treats scalability, reproducibility, security, migration paths, and recovery as design constraints.

## Operator workflow

Review first:

```bash
make plan
```

Apply the current baseline:

```bash
make bootstrap
```

Verify it:

```bash
make verify
```

Test recovery:

```bash
make restore-test
```

## What bootstrap changes

- validates rootless Podman and local secrets
- preserves the isolated internal service network
- resolves the PostgreSQL tag to an immutable digest
- applies versioned SQL migrations
- separates Birdynator's runtime login from schema ownership
- makes canonical memory independent from embedding models
- adds provenance and lifecycle fields
- creates a logical backup
- installs a rootless PostgreSQL Quadlet with CPU/RAM/PID limits
- enables user lingering for boot-time rootless services
- verifies key security properties

## Database privilege model

`birdynator_owner` is a NOLOGIN ownership/migration role.

`birdynator` is the runtime login. It may use approved data but must not own or alter the schema.

## Memory model

Canonical memory remains authoritative text/metadata. Embeddings live in `memory_embeddings` and reference `embedding_models`.

This permits model revisions and different dimensions to coexist during migrations instead of tying decades of memory to one embedding model.

Authoritative BirdNET/weather/source data should remain domain data, not self-authored agent memory. Birdynator conclusions should retain provenance back to source data.

## Recovery

`make backup` creates a logical PostgreSQL dump plus global role definitions with restrictive file permissions.

The default backup location is still on the VM. Configure `config/runtime.local.env` to point `AI_NEXUS_BACKUP_DIR` at an off-VM mounted destination for stronger recovery.

`make restore-test` restores the latest dump into a temporary database, validates it, and deletes the test database.

## Secrets

Local secret files remain under the runtime secrets directory and are never committed. Podman secrets are recreated from those local files when needed.
