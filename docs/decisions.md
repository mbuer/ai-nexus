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

Rationale:

- CPU remains intentionally lean and can be increased based on measured demand.
- 8 GB RAM provides headroom for multiple lightweight services and agent workloads.
- 32 GB is sufficient for an API/cloud-model-first platform.
- Large local models should use expanded or separate storage later.

## 2026-09-23 — Virtual hardware

Selected:

- q35 machine type
- OVMF / UEFI
- VirtIO networking
- VirtIO SCSI
- Proxmox firewall enabled on VM NICs

The Proxmox firewall setting makes the NIC eligible for Proxmox firewall policy; it does not by itself create a restrictive ruleset.

## 2026-09-23 — Repository

Repository: `mbuer/ai-nexus`

The repository is the source of truth for architecture, decisions, configuration, and future automation.

Secrets, passwords, API keys, private SSH keys, and sensitive runtime data must not be committed.

## 2026-09-23 — Network isolation

A dedicated Proxmox bridge (`vmbr1`) and OPNsense AI interface (`10.50.0.1/24`) were selected instead of attaching AI Nexus directly to the home LAN.

The home network remains independent of OPNsense. The AI segment intentionally depends on it so all routed AI traffic passes through one enforcement and observability point.

## 2026-09-23 — Single network path

The temporary main-LAN NIC was removed after the isolated path was validated.

AI Nexus now uses only:

```text
10.50.0.10 -> 10.50.0.1 -> OPNsense
```

This eliminates the previous IPv4 fallback path and IPv6 bypass through the home LAN.

## 2026-09-23 — Controlled Internet access

AI Nexus uses OPNsense for:

- DNS
- HTTP/HTTPS egress
- outbound NAT
- firewall logging

The intent is to tighten outbound access over time rather than granting unrestricted egress by default.

## 2026-09-23 — Management access

Remote management uses WireGuard.

Current explicit access:

```text
10.10.10.0/24 -> 10.50.0.10:22
```

Local laptop access uses a static route through OPNsense because the Spectrum router does not provide the required route to the AI subnet.

This is a pragmatic client-side workaround, not part of the AI security boundary.

## 2026-09-23 — IPv6

IPv6 is not enabled on the AI segment.

This is deliberate. IPv6 will only be introduced once routing, firewall policy, and observability are designed explicitly for it.
