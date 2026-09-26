# AI Nexus

AI Nexus is a secure, reproducible home-lab platform for running isolated AI agents with explicit network, data, secret, and recovery boundaries.

The first real agent is **Birdynator**, a long-term personal bird analyst.

## Current platform

- Debian 13 VM on Proxmox
- OPNsense as the AI segment gateway, DNS, NAT, firewall, and egress-policy point
- WireGuard-only management path
- host nftables defense in depth
- rootless Podman + Quadlet/systemd
- PostgreSQL 17 + pgvector for durable agent state
- local 384-dimensional embedding service
- controlled OpenAI API access through a dedicated CONNECT proxy
- read-only BirdNET PostgreSQL access through a separate fixed-destination datasource proxy
- logical PostgreSQL backup + verified restore workflow

Exact live addresses and credentials are intentionally excluded from this public repository.

## Birdynator

Birdynator currently supports:

- structured canonical memory with provenance and lifecycle fields
- model-versioned semantic embeddings
- memory-aware OpenAI reasoning
- manual model tiers:
  - fast: `gpt-5.6-luna`
  - default: `gpt-5.6-terra`
  - deep: `gpt-5.6-sol`
- real BirdNET + weather analysis
- recent-window versus historical-baseline comparison
- historical mean, standard deviation, percentiles, min/max, and sample counts
- recent species-by-hour and confidence context
- persisted analysis history with source-window provenance and a source-context digest

Default BirdNET analysis compares the latest 24 hours with the preceding 30-day baseline.

See [Birdynator analysis](docs/birdynator-analysis.md).

## Security model

```text
                                  Internet
                                     |
                               Home router
                                     |
                                  HOME_LAN
                                     |
                                  OPNsense
                  gateway / firewall / NAT / DNS / logging
                         /            |             \
                        /             |              \
             WireGuard mgmt       AI segment       HOME_LAN services
                                      |                 |
                                      v                 v
                               AI Nexus host         Infra VM
                             Debian + nftables          |
                                      |                 |
                               rootless Podman          |
                                      |                 |
                              +--- Birdynator ---+      |
                              |        |         |      |
                              |        |         |      |
                       PostgreSQL   OpenAI    BirdNET   |
                                  CONNECT     proxy     |
                                   proxy        |       |
                                      |         +-------+
                                      |
                                      v
                               api.openai.com
                                      ^
                                      |
                               OPNsense / NAT
                                      |
                                   Internet
```

The important point is that **all routed traffic from the AI segment leaves through OPNsense**:

- OpenAI traffic: Birdynator -> OpenAI CONNECT proxy -> AI Nexus host -> OPNsense -> Internet -> `api.openai.com:443`.
- BirdNET datasource traffic: Birdynator -> BirdNET fixed-destination proxy -> AI Nexus host -> OPNsense -> HOME_LAN -> Infra VM/PostgreSQL.
- Management traffic: management client -> WireGuard on OPNsense -> AI Nexus.
- Birdynator's own PostgreSQL and embedding service remain local to AI Nexus on internal Podman networks and do not traverse OPNsense.

The security model is layered:

- **OPNsense** is the Layer-3 enforcement point for the AI segment. It provides the AI gateway, firewall policy, NAT, DNS, WireGuard management ingress, routed access to approved LAN services, and upstream egress control/logging.
- **Debian nftables** provides host-level defense in depth with default-drop inbound/forward policy.
- **Rootless Podman networks and dedicated proxies** form the workload-capability boundary. Birdynator does not receive broad LAN or Internet access merely because one approved service needs it.
- **PostgreSQL roles and separate databases** form the data-permission boundary.

Important properties:

- Birdynator has no host-published port.
- The agent does not receive direct general Internet access.
- OpenAI egress is restricted to `api.openai.com:443` through a dedicated proxy and still traverses OPNsense.
- BirdNET access uses a dedicated read-only database role and traverses OPNsense to the approved Infra-hosted datasource.
- The datasource proxy is isolated from the agent-memory database network.
- Raw BirdNET rows remain authoritative source data; they are not copied into agent memory.
- Generated analyses are stored separately from canonical memory.

See [Architecture](docs/architecture.md), [Network](docs/network.md), [Agent runtime](docs/agent-runtime.md), and [Security baseline](docs/security-baseline.md).

## Normal operator workflow

Platform and recovery operations:

```bash
make plan
make bootstrap
make verify
make repo-check
make backup
make restore-test
```

`make bootstrap` currently rebuilds the PostgreSQL/runtime foundation used by the platform. It is not yet a complete one-command reconstruction of every modern AI Nexus service.

Normal Birdynator code iteration:

```bash
git pull
make birdynator-update
```

The update target applies pending migrations, reuses the cached Birdynator base image by default, restarts only Birdynator, and verifies its security/data paths.

To deliberately refresh its Python base image:

```bash
BIRDYNATOR_REFRESH_BASE=1 make birdynator-update
```

Run an analysis:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analyze-birdnet
```

List persisted analyses:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analysis-history
```

## State and recovery

AI Nexus separates disposable runtime from durable state.

Durable Birdynator state includes:

- canonical memory
- embeddings and embedding-model metadata
- persisted analysis history

Logical PostgreSQL dumps complement Proxmox snapshots/backups. The logical restore path has been tested.

See [Backup and recovery](docs/backup-recovery.md).

## Repository policy

This repository is public.

Never commit:

- passwords or API keys
- SSH/WireGuard private keys or pre-shared keys
- tokens
- WAN addressing
- exact private addressing/topology from the live environment
- screenshots containing sensitive infrastructure details

Use symbolic names in documentation and keep environment-specific values in ignored local configuration.

## Start here

For a compact overview of the project and the important reading order, see [Executive summary](docs/executive-summary.md).

Detailed references:

- [Architecture](docs/architecture.md)
- [Birdynator analysis](docs/birdynator-analysis.md)
- [Agent runtime](docs/agent-runtime.md)
- [Reproducible runtime](docs/reproducible-runtime.md)
- [Decision log](docs/decisions.md)
- [Network](docs/network.md)
- [Security baseline](docs/security-baseline.md)
- [Backup and recovery](docs/backup-recovery.md)
- [Break-glass recovery](docs/break-glass-recovery.md)
