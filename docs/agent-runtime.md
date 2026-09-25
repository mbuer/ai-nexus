# Agent Runtime

## Purpose

The runtime layer is where AI Nexus executes isolated agents and their supporting services.

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
- Birdynator uses a dedicated least-privilege login role
- schema ownership is separated into a non-login owner role

## Local embedding service

Birdynator uses a local sentence-transformer embedding service.

Verified properties:

- `sentence-transformers/all-MiniLM-L6-v2`
- pinned model revision
- 384-dimensional vectors
- CPU-only PyTorch runtime
- internal-only Podman networking
- no host-published port
- read-only container filesystem with bounded temporary storage
- model-independent canonical memory with embeddings stored separately in PostgreSQL

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
- access to the local embedding service
- no host-published ports
- internal-only Podman networking
- rootless Quadlet/systemd lifecycle
- bounded CPU, memory, and PID resources
- a read-only container filesystem

The Birdynator credential is provided through a Podman secret.

Agents should never receive the PostgreSQL superuser credential.

## Model routing

Birdynator is configured for tiered OpenAI model routing:

```text
fast/default-low-cost: gpt-5.6-luna
normal/default:         gpt-5.6-terra
deep/escalation:        gpt-5.6-sol
```

The OpenAI API credential remains a local runtime secret and is never committed to Git.

Birdynator reaches the OpenAI API only through a dedicated CONNECT proxy. The proxy allows the approved OpenAI API destination on TCP/443, preserves end-to-end TLS, is not attached to the agent-memory database network, and publishes no host port. Birdynator itself has no direct general Internet egress.

## Structured and semantic memory

Canonical memory remains model-independent.

Memory records include provenance and lifecycle fields such as:

- memory type
- content
- metadata
- source type
- source reference
- observation time
- confidence
- status
- supersession link

Embeddings are stored separately and linked to a registered embedding-model version.

This allows the embedding model to change later without rewriting or redefining canonical memory.

## Verified deployment

The Birdynator runtime has been built and deployed successfully.

Verified:

- Birdynator container starts successfully
- Birdynator authenticates to PostgreSQL as the least-privilege `birdynator` role
- local embedding service is reachable from the agent
- expected 384-dimensional embedding model is available
- no host port is published
- agent remains on the internal-only Podman network
- deployment is reproducible through `make birdynator-build`, `make birdynator-deploy`, and `make birdynator-verify`

Semantic memory is also validated end to end:

- `remember` creates a canonical memory record
- the local embedding service generates the vector
- pgvector stores the embedding separately from canonical memory
- `recall` retrieves semantically relevant memory

Controlled OpenAI reasoning is now validated:

- Birdynator has no direct Internet egress
- OpenAI access goes through the dedicated allowlist proxy
- the proxy is restricted to `api.openai.com:443`
- the proxy is not attached to the PostgreSQL service network
- the OpenAI API secret is mounted only into Birdynator
- `ask` retrieves relevant local memories before calling the Responses API
- the default Terra tier and explicit Sol deep tier both returned the correct answer from retrieved memory
- Responses API requests use `store: false`

## Next steps

1. Test multi-observation reasoning and hypothesis formation.
2. Add explicit model-tier selection/escalation logic beyond manual `--tier`.
3. Add structured provenance to generated analytical conclusions.
4. Add observability for agent requests, model tier, latency, and token/cost usage without logging secrets or full private prompts by default.
5. Continue recovery validation after agent memory and reasoning state expand.


## BirdNET datasource

BirdNET PostgreSQL remains an authoritative external datasource rather than becoming agent memory.

Birdynator reaches it through a separate fixed-destination proxy:

```text
Birdynator
    -> ai-nexus-birdnet-link
    -> BirdNET fixed-destination proxy
    -> BirdNET PostgreSQL
```

Security properties:

- dedicated read-only PostgreSQL role
- database sessions force `default_transaction_read_only=on`
- proxy is not attached to the agent-memory service network
- proxy publishes no host port
- Birdynator is not given general LAN access
- raw BirdNET rows are not duplicated into canonical memory

See `docs/birdynator-analysis.md`.

## Analysis history

Generated BirdNET analyses are durable state, but they are not source truth and are kept separate from canonical memory.

The `analysis_runs` table stores:

- model
- source reference/window
- recent/baseline parameters
- digest of the exact reasoning context
- generated analysis text
- creation time

This keeps analysis provenance without copying the BirdNET dataset.

## Fast development workflow

For normal Birdynator code changes:

```bash
git pull
make birdynator-update
```

The update target applies migrations, rebuilds only Birdynator, restarts it, and runs its verification checks. The cached Python base image is reused unless `BIRDYNATOR_REFRESH_BASE=1` is explicitly set.

The container build runs `python -m py_compile` so syntax errors fail during image construction instead of at first execution.
