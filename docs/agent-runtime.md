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

## Per-agent database identity

The first agent has:

- a dedicated PostgreSQL login role
- a dedicated database
- a separate credential
- no PostgreSQL superuser or role-management privileges

The agent credential is also provided through a Podman secret.

Agents should never receive the PostgreSQL superuser credential.

## Structured memory

The first memory table is owned by the agent database role.

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

Indexes exist for memory type and JSON metadata.

The initial model deliberately separates structured memory from future semantic/vector search.

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

1. Add pgvector support.
2. Define embedding generation and semantic-memory policy.
3. Create the first real agent container.
4. Limit each agent to only the database, tools, files, and network capabilities it needs.
5. Define backup and restore procedures for persistent agent state.
6. Move important audit/telemetry off the agent host over time.
