# Decision Log

## 2026-09-23 — Platform scope

AI Nexus will be treated as a long-term secure agent execution platform rather than a general-purpose AI VM.

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

Reasoning:

- CPU remains intentionally lean and can be increased based on measured demand.
- 8 GB RAM provides headroom for multiple lightweight services and agent workloads.
- 32 GB is sufficient for an API/cloud-model-first platform; large local models should use separate or expanded storage later.

## 2026-09-23 — Virtual hardware

Selected:

- q35 machine type
- OVMF / UEFI
- VirtIO networking
- VirtIO SCSI
- Proxmox firewall enabled on VM NICs

The Proxmox firewall checkbox enables the NIC to participate in future firewall policy; it does not by itself impose a restrictive policy.

## 2026-09-23 — Repository

Repository: `mbuer/ai-nexus`

The repository is the source of truth for architecture, decisions, configuration, and future automation. Secrets and private keys must never be committed.

## 2026-09-23 — Network isolation

A dedicated internal Proxmox bridge (`vmbr1`) and OPNsense AI interface (`10.50.0.1/24`) were selected instead of leaving AI workloads directly attached to the home LAN.

The normal home network should not depend on OPNsense. The AI segment may depend on it because OPNsense is intentionally the enforcement and observability boundary for agent traffic.

## 2026-09-23 — Migration strategy

The existing LAN interface remains connected temporarily while the isolated path is tested.

The direct LAN path will only be removed after:

1. Persistent AI addressing works.
2. DNS and Internet egress work through OPNsense.
3. Firewall logging is verified.
4. WireGuard/management access to the AI subnet works.

This avoids losing management access during the migration.
