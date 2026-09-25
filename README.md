# AI Nexus

Secure, reproducible home-lab platform for running isolated AI agents with controlled access and observability.

## Current status

The base VM, isolated AI network, controlled egress, WireGuard management path, rootless container runtime, and first agent memory service are operational.

### VM baseline

- Hypervisor: Proxmox
- VM: `ai-nexus`
- OS: Debian 13.7 (Trixie)
- Kernel: `6.12.107+deb13-amd64`
- CPU: 2 vCPU
- RAM: 8 GB
- Disk: 32 GB
- Machine: q35
- Firmware: OVMF / UEFI
- NIC model: VirtIO
- Proxmox firewall: enabled
- QEMU guest agent: installed

Known recovery snapshots:

- `baseline-pre-network-segmentation`
- post-network-cleanup snapshot taken after the isolated network and WireGuard management path were established
- `baseline-ssh-firewall-hardening`
- `baseline-security-audit`
- `baseline-agent-memory`

## Network model

AI Nexus is isolated from the main LAN and uses OPNsense as its only Layer-3 gateway.

Public documentation intentionally uses symbolic names instead of the live environment's exact addressing:

```text
Internet
   |
Home router
   |
HOME_LAN
   |
OPNsense
   +-- WG_NET
   |
AI_GATEWAY
   |
vmbr1
   |
AI_HOST
```

Validated:

- AI Nexus -> OPNsense reachability
- DNS via OPNsense
- HTTPS egress via OPNsense
- outbound NAT
- firewall logging
- remote SSH over WireGuard
- home SSH over a dedicated WireGuard peer, with intermittent resets still under investigation
- normal home-lab access remains local while the Home profile is active
- client-side static-route workaround removed
- GitHub SSH works over TCP/443 without opening generic outbound TCP/22

## Host security baseline

Current Debian hardening includes:

- direct root SSH disabled
- SSH key and password authentication retained for the non-root admin account
- persistent nftables host firewall with default-drop inbound/forward policy
- SSH accepted only from the WireGuard management network
- outbound host policy left open; OPNsense remains the primary egress enforcement point
- automatic Debian security/stable upgrades enabled without automatic reboot
- persistent systemd journal storage
- auditd enabled with targeted watches for SSH, sudoers, nftables, identity files, and systemd unit configuration

See `docs/security-baseline.md`.

## Management access

AI Nexus management uses WireGuard both at home and away.

Home and Away use **separate peer identities and keypairs**.

- Home profile routes only `AI_NET` through WireGuard and uses the firewall's local LAN endpoint.
- Away profile routes both `HOME_LAN` and `AI_NET` through WireGuard and uses the public endpoint.

Exact live addresses are intentionally not stored in this public repository.

## Agent runtime

The first runtime layer is now operational:

- Podman 5.4.x
- rootless containers under the non-root admin account
- `crun` OCI runtime
- `netavark` networking
- journald container logging
- seccomp enabled
- dedicated internal Podman network for service-to-service traffic

The internal service network is intentionally not documented with its live subnet.

### Agent memory service

PostgreSQL 17 is running as a rootless container on the isolated internal Podman network.

Current model:

- no PostgreSQL host port is published
- persistent database storage uses a Podman volume
- PostgreSQL superuser credential is stored locally and exposed to the container through a Podman secret
- the first named agent is **Birdynator**, a long-term personal bird analyst
- Birdynator has its own database role and database
- the Birdynator role has no elevated PostgreSQL attributes
- the Birdynator credential is separate from the PostgreSQL superuser credential
- the `memory` table is owned by Birdynator
- authenticated read/write access was verified from a separate temporary container
- pgvector 0.8.6 is enabled in the Birdynator database
- the memory schema now includes a `vector(384)` embedding column with an HNSW cosine index

See `docs/agent-runtime.md`.

## Controlled GitHub access

The repository remote uses SSH, but generic outbound TCP/22 is intentionally not opened from the AI subnet.

AI Nexus therefore uses GitHub's supported SSH-over-443 endpoint via `~/.ssh/config`:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

## Why this design

The consumer home router does not provide the static-routing flexibility needed for an elegant direct LAN -> AI subnet path while OPNsense remains a secondary router.

A client-side static route was tested but produced unstable SSH sessions. Reusing the same WireGuard peer identity for both Home and Away profiles also produced instability.

The final management design uses separate WireGuard peers and keeps OPNsense as the single enforcement and observation point for the AI segment.

## Public-repository policy

Architecture and decisions are public; live addressing is not.

Use:

- `config/network.example.yaml` for safe example values
- `config/network.local.yaml` for real local values

The local file is ignored by Git.

Never commit passwords, API keys, private SSH keys, WireGuard private keys, pre-shared keys, tokens, WAN addresses, or screenshots containing sensitive network details.

## Design goals

- secure agent execution
- reproducible infrastructure
- default-deny network boundaries
- least-privilege access
- centralized observability and auditability
- separation of agent runtime, tools, data, and secrets
- human approval for sensitive or destructive actions

## Next steps

1. Continue observing Home WireGuard stability and capture the next failure without restarting the tunnel.
2. Add reproducible configuration management.
3. Add the local embedding service and populate Birdynator's semantic memory vectors.
4. Define Birdynator's first real agent container and per-agent permissions.
5. Formalize secrets handling and backup/recovery for agent state.
6. Add centralized off-host logging and metrics.
7. Review and tighten OPNsense egress rules as agent requirements become known.

See `docs/` for architecture, networking, management access, troubleshooting history, and decision records.
