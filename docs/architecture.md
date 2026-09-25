# Architecture

## Purpose

AI Nexus is a home-lab execution platform for AI agents.

The architecture prioritizes:

- containment
- reproducibility
- explicit permissions
- controlled network access
- independent observability
- recoverability

## Principles

- Agents request capabilities; the platform grants and enforces them.
- The agent runtime does not implicitly trust the surrounding LAN.
- Read and write capabilities should be separated.
- Sensitive actions should require explicit approval.
- Secrets must remain outside source control.
- Workloads should be disposable where practical.
- Persistent state should be separated from disposable runtimes.
- Audit data should eventually leave the agent VM so the agent cannot erase the only record of its actions.
- Management access should use a narrow, explicit path rather than broad LAN exposure.

## Current platform

```text
                         Internet
                            |
                       Home router
                            |
                         HOME_LAN
                            |
                         OPNsense
                       /            \
                    WG_NET        AI_GATEWAY
                                      |
                                    vmbr1
                                      |
                                   AI_HOST
```

Exact live IP addresses are intentionally omitted from this public repository.

## AI Nexus VM

- Debian 13.7
- kernel `6.12.107+deb13-amd64`
- 2 vCPU
- 8 GB RAM
- 32 GB disk
- q35
- OVMF / UEFI
- VirtIO networking
- VirtIO SCSI
- QEMU guest agent
- single active network path through `vmbr1`

The previous direct home-LAN NIC has been removed.

## Security boundaries

### 1. Proxmox VM boundary

AI Nexus is its own VM rather than sharing the operating system of other home-lab services.

### 2. Dedicated Layer-2 segment

The AI network exists on `vmbr1`, an internal Proxmox bridge with no physical uplink and no Proxmox host address.

### 3. OPNsense Layer-3 boundary

OPNsense is the only gateway for AI Nexus.

This centralizes:

- firewall enforcement
- DNS
- NAT
- egress control
- traffic logging
- management ingress

### 4. Debian host boundary

AI Nexus now has its own minimal nftables policy in addition to OPNsense:

- default-drop inbound and forwarding
- loopback allowed
- established/related traffic allowed
- SSH accepted only from the WireGuard management network
- ICMP/ICMPv6 allowed for diagnostics
- outbound traffic accepted locally and still governed upstream by OPNsense

The host also uses unattended upgrades, persistent journald, and targeted auditd rules.

### 5. WireGuard management boundary

AI Nexus is not managed directly from the normal LAN.

SSH management arrives through WireGuard:

```text
management client
    -> WireGuard
    -> OPNsense
    -> AI_HOST:22
```

## Agent runtime layer

AI Nexus now uses rootless Podman for containerized workloads.

Current runtime characteristics:

- containers run without a privileged Docker daemon
- OCI runtime: `crun`
- network backend: `netavark`
- container logs use journald
- seccomp is enabled
- persistent container state is separated from disposable container instances

### Internal service network

A dedicated internal Podman network provides service-to-service connectivity between agents and supporting services.

The live container subnet is intentionally omitted from the public repository.

### PostgreSQL memory service

The first shared service is PostgreSQL 17.

Design:

```text
agent container
      |
      | internal Podman network
      |
PostgreSQL
```

PostgreSQL is not published to the AI Nexus host or LAN.

The first named agent is **Birdynator**, a long-term personal bird analyst.

Birdynator uses:

- its own database role
- its own database
- its own credential
- an agent-owned memory table

The PostgreSQL superuser credential is not exposed to Birdynator.

The initial memory schema stores:

- memory type
- content
- JSON metadata
- creation timestamp
- update timestamp
- 384-dimensional vector embedding

pgvector 0.8.6 is enabled in the Birdynator database. The embedding column uses `vector(384)` and an HNSW index with cosine distance. The next runtime component is the local embedding service that will populate and query those vectors.

## Deliberate asymmetry

The AI segment depends on OPNsense.

The normal home LAN does not.

This allows strict AI controls without making the entire home network dependent on a Proxmox-hosted firewall VM.

## Home vs remote management

Two WireGuard client profiles use separate peer identities.

### Home

```text
Endpoint: local OPNsense LAN address
AllowedIPs: AI_NET
```

Only AI-subnet traffic enters WireGuard. Normal home-lab traffic remains directly connected.

### Away / work

```text
Endpoint: public WireGuard endpoint
AllowedIPs:
  HOME_LAN
  AI_NET
```

Both home-lab and AI-subnet traffic enter WireGuard.

## Failure behavior

### OPNsense unavailable

Expected:

- AI Nexus loses routed Internet access
- AI Nexus loses DNS through OPNsense
- WireGuard management path to AI Nexus is unavailable
- ordinary home LAN devices continue operating through the home router

### Home Internet unavailable

Expected:

- local Home WireGuard management should still work
- remote WireGuard access is unavailable
- AI Nexus loses Internet egress

### AI Nexus unavailable

No effect on the home LAN or OPNsense.

### Backup trust boundary

Logical backups should ultimately leave the AI Nexus VM.

Preferred properties:

- backup storage is outside the agent VM
- the agent runtime cannot freely alter historical backups
- transfer access is narrower than general host access
- restore procedures are tested, not assumed
- VM snapshots and logical database backups are complementary rather than interchangeable

The current logical backup mechanism is verified; off-host placement is the next recovery hardening step.

## Recovery checkpoints

A baseline snapshot exists from before network segmentation.

Additional recovery checkpoints were taken after SSH/firewall hardening and after the security/audit baseline was completed. `baseline-agent-memory` captures the rootless Podman, PostgreSQL, and first-agent memory milestone.

Snapshots are recovery aids, not configuration management.

## Planned platform layers

1. Proxmox VM boundary
2. OPNsense network enforcement
3. Hardened Debian host — baseline complete
4. Containerized workloads — rootless Podman baseline operational
5. Per-agent identities and permissions — Birdynator database identity operational
6. Secrets management — local Podman-secret pattern established
7. Centralized logging and metrics
8. Versioned agent definitions and infrastructure configuration
9. Automated rebuild and recovery procedures
