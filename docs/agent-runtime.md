# Agent Runtime

## Purpose

The runtime layer is where AI Nexus begins executing isolated agents and their supporting services.

The current design keeps the Debian host as the security boundary and runs workloads as rootless containers on top of it.

## Container runtime

Podman is the initial runtime.

Verified baseline:

- Podman 5.4.x
- rootless execution
- `crun` OCI runtime
- `netavark` networking
- journald logging
- seccomp enabled

A minimal Alpine container was pulled and executed successfully as the non-root admin user.

## Runtime directory layout

Local runtime state is organized conceptually as:

```text
ai-nexus-runtime/
├── agents/
├── services/
├── data/
└── secrets/
```

The exact local path is environment-specific.

Purpose:

- `agents/` — agent definitions and runtime configuration
- `services/` — supporting service definitions
- `data/` — persistent application data
- `secrets/` — local credentials that must never be committed

## Internal service network

A dedicated Podman network provides private service-to-service connectivity.

The network is configured as internal and has container DNS enabled.

The live subnet is intentionally not documented publicly.

## PostgreSQL memory service

PostgreSQL 17 is the first shared runtime service.

Security properties:

- runs rootless
- attached only to the internal service network
- no host port is published
- persistent data lives in a Podman volume
- the superuser password is stored in a local `600` file
- the secret is injected through Podman rather than placed in the container command line

## Birdynator

The first named agent is **Birdynator**.

Birdynator is intended to be a long-term personal bird analyst that builds continuity across observations, environmental data, analysis, and time.

Technical identity:

```text
slug:      birdynator
container: agent-birdynator
database:  birdynator
DB role:   birdynator
DB secret: birdynator-db-password
```

Birdynator has:

- a dedicated PostgreSQL login role
- a dedicated database
- a separate credential
- no PostgreSQL superuser or role-management privileges

The Birdynator credential is provided through a Podman secret.

Agents should never receive the PostgreSQL superuser credential.

## Structured memory

The first memory table is owned by the Birdynator database role.

Schema concept:

```text
memory
├── id
├── memory_type
├── content
├── metadata (JSONB)
├── created_at
└── updated_at
```

Indexes exist for memory type and JSON metadata. pgvector 0.8.6 is enabled, and the embedding column has an HNSW cosine index.

Structured fields remain the authoritative memory record; vector search is an additional retrieval mechanism rather than a replacement for structured data.

Example memory categories may include:

- preference
- fact
- task
- observation
- note

These categories are a starting convention, not a hard platform constraint.

## Validation

The memory path was verified from a separate temporary container using only the agent credential.

Validated:

- service-name DNS resolution on the internal Podman network
- PostgreSQL reachability
- agent authentication
- insert into the agent-owned memory table
- read-back of the inserted record

The PostgreSQL superuser credential was not required by the agent-side validation.

## Next steps

1. Add a local embedding service for Birdynator.
2. Define embedding generation and semantic-memory policy.
3. Populate and query Birdynator's first semantic memory vectors.
4. Create the first real Birdynator agent container.
5. Limit each agent to only the database, tools, files, and network capabilities it needs.
6. Define backup and restore procedures for persistent agent state.
7. Move important audit/telemetry off the agent host over time.
