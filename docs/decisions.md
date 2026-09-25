# Decision Log

## 2026-09-23 — Platform scope

AI Nexus is a long-term secure agent execution platform rather than a general-purpose AI VM.

Primary qualities:

- secure
- scalable
- reproducible
- observable
- least privilege

## 2026-09-23 — Initial VM sizing

Selected baseline:

- 2 vCPU
- 8 GB RAM
- 32 GB disk

## 2026-09-23 — Virtual hardware

Selected:

- q35 machine type
- OVMF / UEFI
- VirtIO networking
- VirtIO SCSI
- Proxmox firewall enabled on VM NICs

## 2026-09-23 — Repository

Repository: `mbuer/ai-nexus`

The repository is the source of truth for architecture, decisions, configuration, and future automation.

Secrets and live environment-specific addressing must not be committed.

## 2026-09-23 — Network isolation

A dedicated Proxmox bridge (`vmbr1`) and dedicated OPNsense AI interface were selected instead of attaching AI Nexus directly to the home LAN.

The home network remains independent of OPNsense. The AI segment intentionally depends on it.

## 2026-09-23 — Single network path

AI Nexus uses only:

```text
AI_HOST -> AI_GATEWAY -> OPNsense
```

The temporary direct-LAN NIC was removed.

## 2026-09-23 — Controlled Internet access

AI Nexus uses OPNsense for:

- DNS
- HTTP/HTTPS egress
- outbound NAT
- firewall logging

Generic outbound TCP/22 is not intentionally permitted.

## 2026-09-23 — DNS through OPNsense

AI Nexus uses OPNsense as its DNS resolver.

`resolvconf` is installed and the DNS resolver is part of the persistent Debian interface configuration.

## 2026-09-23 — GitHub SSH over 443

The Git remote remains SSH-based, but GitHub SSH is redirected to `ssh.github.com:443`.

This avoids opening generic outbound TCP/22 solely for repository access.

## 2026-09-23 — Reject client-side static routing as normal management

A Windows persistent route to the AI subnet through OPNsense was tested and later removed.

The path was operationally complex and unstable.

## 2026-09-24 — Separate WireGuard peers for Home and Away

The original Home profile reused the Away peer identity.

That produced intermittent failures:

- SSH reset after initially working
- subsequent SSH attempts timed out
- restarting the tunnel temporarily restored access

The final design uses distinct peers and separate keypairs.

### Home

```text
Endpoint = local OPNsense LAN address
AllowedIPs = AI_NET
PersistentKeepalive = 25
```

### Away / work

```text
Endpoint = public WireGuard endpoint
AllowedIPs = HOME_LAN, AI_NET
```

The Home session was verified as originating from the dedicated Home peer. Separate peer identities remain the correct architecture, but later testing showed that intermittent SSH resets can still occur, so peer reuse was not the sole cause.

## 2026-09-24 — Sanitize public network documentation

The repository remains public, but exact live network addressing is no longer part of public documentation.

Rationale:

- RFC1918 addresses are not Internet-routable, but publishing exact topology and management addressing provides unnecessary environmental detail.
- The learning value is preserved by documenting roles and relationships symbolically.
- Real values belong in a local ignored configuration file.

Pattern:

```text
config/network.example.yaml   # safe example
config/network.local.yaml     # real values, ignored
```

## 2026-09-23 — Troubleshooting changes are not architecture

The following are not part of the intended final architecture:

- explicit LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- per-rule `Disable reply-to`
- global `Disable force gateway`
- Windows persistent route

## 2026-09-23 — IPv6

IPv6 is not enabled on the AI segment.

## 2026-09-23 — Snapshot after network cleanup

A recovery snapshot was taken after the isolated networking and management path were established.

Snapshots are recovery checkpoints, not a substitute for configuration management.


## 2026-09-24 — Debian security baseline

The Debian host now provides defense in depth in addition to OPNsense.

SSH:

- direct root SSH disabled with `PermitRootLogin no`
- public-key authentication enabled
- password authentication intentionally retained for the non-root admin account

Host firewall:

- nftables enabled persistently
- inbound and forwarding default to drop
- loopback and established/related traffic allowed
- SSH accepted only from the WireGuard management network
- ICMP and ICMPv6 retained for diagnostics
- outbound traffic accepted locally; OPNsense remains the primary egress policy boundary

Updates and logging:

- unattended upgrades enabled for the current Debian release and Debian security origins
- package lists and unattended upgrades run daily
- automatic reboot remains disabled
- systemd journal storage is persistent
- auditd and audispd plugins enabled
- targeted audit watches cover SSH configuration, sudoers, nftables configuration, local identity files, and systemd unit configuration
- an audit test confirmed configuration changes are recorded with user attribution

## 2026-09-24 — Security baseline snapshot

Snapshot:

```text
baseline-security-audit
```

Description:

```text
Hardened Debian baseline with root SSH disabled, nftables host firewall, unattended upgrades, persistent journald, and targeted auditd rules verified.
```


## 2026-09-24 — Rootless Podman runtime

Podman was selected as the initial container runtime.

Rationale:

- supports rootless containers cleanly
- avoids making a privileged Docker daemon a general agent capability
- integrates with systemd/journald
- supports per-container networking and secrets
- fits the least-privilege design of AI Nexus

The verified runtime uses `crun`, `netavark`, journald logging, and seccomp.

## 2026-09-24 — Internal container service network

A dedicated internal Podman network is used for agent-to-service communication.

Design goals:

- supporting services are not published to the host or LAN by default
- agents can reach only the services attached to the same internal network
- live container subnet details remain environment-specific and are not stored in the public repository

## 2026-09-24 — PostgreSQL as the initial agent memory backend

PostgreSQL 17 was selected as the first persistent memory backend.

Initial design:

- PostgreSQL runs as a rootless container
- no host port is published
- persistent data uses a Podman volume
- the PostgreSQL superuser credential is stored locally and injected through a Podman secret
- each agent receives a separate database identity rather than using the PostgreSQL superuser
- the first agent has its own role and database
- the first agent role has no elevated PostgreSQL attributes

The initial memory schema is intentionally structured and simple. Vector search will be added later rather than introducing a separate vector database at this stage.

## 2026-09-24 — First agent memory validation

The first agent database path was validated end to end:

```text
agent credential
    -> internal Podman network
    -> PostgreSQL
    -> agent-owned memory table
```

A temporary container authenticated using the agent credential, inserted a structured memory record, and successfully read it back.

This proves the first per-agent persistence boundary before deploying a real agent process.


## 2026-09-24 — First agent identity: Birdynator

The generic first-agent identity was renamed to **Birdynator**.

Purpose:

> A long-term personal bird analyst that builds continuity across observations, environmental data, analysis, and time.

Technical naming:

```text
display name: Birdynator
slug:         birdynator
container:    agent-birdynator
database:     birdynator
DB role:      birdynator
DB secret:    birdynator-db-password
```

The PostgreSQL role, database, and local/Podman credential naming were updated to match. Birdynator retains ownership of the existing memory table and has no elevated PostgreSQL privileges.

## 2026-09-24 — pgvector semantic-memory foundation

The PostgreSQL service image was changed from the standard PostgreSQL 17 image to the pgvector PostgreSQL 17 image while reusing the existing persistent Podman volume.

Validation confirmed that the existing Birdynator memory record survived the image change.

The `vector` extension is enabled in the Birdynator database:

```text
pgvector 0.8.6
```

The memory table now includes:

- `embedding vector(384)`
- HNSW index using `vector_cosine_ops`

The 384-dimensional shape is intended for a small local sentence-transformer embedding model. The embedding service itself is the next step.

## 2026-09-24 — Agent memory snapshot

Snapshot:

```text
baseline-agent-memory
```

This snapshot marks the first complete agent persistence milestone: rootless Podman runtime, isolated service network, PostgreSQL-backed per-agent memory, and verified Birdynator database identity.
