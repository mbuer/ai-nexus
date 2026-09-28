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

Verify the complete deployed runtime (foundation, embedding service, both proxies, and Birdynator):

```bash
make verify
```

`make bootstrap` installs only the PostgreSQL/runtime foundation. On a foundation-only host, use `bash scripts/verify.sh`; deploy the supporting services and Birdynator before running `make verify`. The full check runs in dependency order and stops at the first failure. Birdynator verification requires working OpenAI API and BirdNET datasource access.

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

The default backup location is still on the VM and should be treated as a staging location, not the final recovery boundary.

The verified off-VM chain uses a [Proxmox backup hook](proxmox-backup-hook.md) to create a fresh logical PostgreSQL backup before the VM archive is written to external backup storage. The hook aborts the VM backup if the logical backup fails. The external VM archive provides the durable off-host copy without mounting broad writable backup storage into the agent VM. See [Backup and recovery](backup-recovery.md).

`make restore-test` restores the latest dump into a temporary database, validates it, and deletes the test database.

## Secrets

Local secret files remain under the runtime secrets directory and are never committed. Podman secrets are recreated from those local files when needed.


## Verified recovery milestone

The first restore test completed successfully.

Validated:

- the logical dump restored into a temporary database
- the existing Birdynator memory record was recovered
- the `memory_embeddings` table was present
- pgvector restored correctly when recovery ran under the PostgreSQL administrative role
- the temporary restore-test database was removed afterward

This confirms that the current logical backup is not merely being created; it is usable for recovery.


## Birdynator iteration

For normal Birdynator code changes, use the narrow update path:

```bash
git pull
make birdynator-update
```

This:

1. applies pending SQL migrations
2. reuses the cached Python base image by default
3. rebuilds only the Birdynator image
4. restarts only the Birdynator service
5. runs Birdynator-specific verification

To deliberately refresh the Python base image:

```bash
BIRDYNATOR_REFRESH_BASE=1 make birdynator-update
```

The image build runs Python bytecode compilation as an early syntax check.

Use the broader deploy targets when supporting proxy/network infrastructure changes.

## Analysis schema

Migration `004_analysis_runs.sql` adds durable analysis history.

It stores generated interpretations and their provenance separately from canonical memory and from authoritative BirdNET source data.

The logical backup workflow automatically includes this table because it is part of the Birdynator PostgreSQL database.
