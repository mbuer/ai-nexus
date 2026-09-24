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

Secrets, passwords, API keys, private SSH keys, WireGuard private keys, and sensitive runtime data must not be committed.

## 2026-09-23 — Network isolation

A dedicated Proxmox bridge (`vmbr1`) and OPNsense AI interface (`10.50.0.1/24`) were selected instead of attaching AI Nexus directly to the home LAN.

The home network remains independent of OPNsense. The AI segment intentionally depends on it.

## 2026-09-23 — Single network path

AI Nexus uses only:

```text
10.50.0.10 -> 10.50.0.1 -> OPNsense
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

AI Nexus uses OPNsense at `10.50.0.1` as its DNS resolver.

`resolvconf` is installed and `dns-nameservers 10.50.0.1` is part of the persistent Debian interface configuration.

## 2026-09-23 — GitHub SSH over 443

The Git remote remains SSH-based, but GitHub SSH is redirected to `ssh.github.com:443`.

This avoids opening generic outbound TCP/22 solely for repository access.

## 2026-09-23 — Reject client-side static routing as normal management

A Windows persistent route to `10.50.0.0/24` via `192.168.1.25` was tested and later removed.

The path was operationally complex and unstable.

## 2026-09-24 — Separate WireGuard peers for Home and Away

The original Home profile reused the Away peer identity.

That produced intermittent failures:

- SSH reset after initially working
- subsequent SSH attempts timed out
- restarting the tunnel temporarily restored access

The final design uses distinct peers:

```text
Away / work peer: 10.10.10.3/32
Home peer:        10.10.10.4/32
```

Each has its own WireGuard keypair.

### Home

```text
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
PersistentKeepalive = 25
```

### Away / work

```text
Endpoint = <public-wireguard-endpoint>:51820
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
```

The Home session was verified on AI Nexus as originating from `10.10.10.4`, and the tunnel remained stable during active use.

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
