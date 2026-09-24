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

Secrets, passwords, API keys, private SSH keys, WireGuard private keys, and sensitive runtime data must not be committed.

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

## 2026-09-23 — DNS through OPNsense

AI Nexus uses OPNsense at `10.50.0.1` as its DNS resolver.

`resolvconf` is installed and `dns-nameservers 10.50.0.1` is part of the persistent Debian interface configuration.

This replaces the temporary manual edit of `/etc/resolv.conf`.

IPv4 DNS and HTTPS egress were verified successfully.

## 2026-09-23 — Remote management

Remote management uses WireGuard.

Current explicit access:

```text
10.10.10.0/24 -> 10.50.0.10:22
```

Remote access from work is stable.

## 2026-09-23 — Reject client-side static routing as the normal management path

A Windows persistent route was tested:

```text
10.50.0.0/24 via 192.168.1.25
```

The route allowed SSH to establish, but the connection later became unstable.

Packet captures showed retransmissions followed by a TCP reset from the Windows client.

The route was removed and is no longer part of the design.

Rationale:

- the Spectrum router does not provide the routing flexibility needed for a clean secondary-router design
- client-specific static routes add operational complexity
- the path was unreliable
- WireGuard already provides a stable, explicit management boundary

## 2026-09-23 — Dual WireGuard client profiles

Management uses two client profiles with the same peer credentials but different endpoint/routing behavior.

### Home profile

```text
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
```

Purpose:

- route only AI-subnet traffic through WireGuard
- keep normal home-lab traffic on the local LAN
- avoid NAT loopback/hairpin dependence on the public endpoint

### Away / work profile

```text
Endpoint = <public-wireguard-endpoint>:51820
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
```

Purpose:

- provide remote access to both normal lab devices and AI Nexus

Only one profile should be active at a time.

## 2026-09-23 — Troubleshooting changes are not architecture

The following were tested while diagnosing the direct-LAN SSH issue:

- explicit LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- per-rule `Disable reply-to`
- global `Disable force gateway`
- Windows persistent route

These are not part of the intended final architecture.

## 2026-09-23 — IPv6

IPv6 is not enabled on the AI segment.

This is deliberate. IPv6 will only be introduced once routing, firewall policy, and observability are designed explicitly for it.

## 2026-09-23 — Snapshot after network cleanup

A recovery snapshot was taken after:

- isolated AI networking
- WireGuard home/remote management
- Windows static-route removal
- persistent DNS configuration
- troubleshooting cleanup

The snapshot is a recovery checkpoint, not a substitute for future configuration management.
