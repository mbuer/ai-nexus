# AI Nexus

Secure, reproducible home-lab platform for running isolated AI agents with controlled access and observability.

## Current status

The base VM, isolated AI network, controlled egress, and WireGuard management path are operational.

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

Known snapshot:

- `baseline-pre-network-segmentation`

A second post-network-cleanup snapshot was taken before this documentation pass.

### Network

AI Nexus is isolated from the main LAN and uses OPNsense as its only gateway.

- Home LAN: `192.168.1.0/24`
- Spectrum router: `192.168.1.1`
- OPNsense LAN: `192.168.1.25`
- WireGuard subnet: `10.10.10.0/24`
- AI subnet: `10.50.0.0/24`
- OPNsense AI interface: `10.50.0.1`
- AI Nexus: `10.50.0.10`
- Proxmox AI bridge: `vmbr1`
- AI Nexus interface: `ens19`
- IPv6: intentionally not used on the AI segment
- Direct LAN NIC on AI Nexus: removed

Validated:

- AI Nexus -> OPNsense reachability
- DNS via OPNsense
- HTTPS egress via OPNsense
- outbound NAT
- firewall logging
- remote SSH over WireGuard
- home SSH over a dedicated local WireGuard profile
- normal home-lab access remains local while the home WireGuard profile is active
- Windows static route workaround removed

### Management access

AI Nexus management now uses WireGuard both at home and away.

#### Away / work profile

```text
Endpoint: public WireGuard endpoint
AllowedIPs:
  192.168.1.0/24
  10.50.0.0/24
```

This provides access to both the normal home lab and AI Nexus when remote.

#### Home profile

```text
Endpoint: 192.168.1.25:51820
AllowedIPs:
  10.50.0.0/24
```

This sends only AI-subnet traffic through WireGuard. Normal `192.168.1.0/24` traffic stays directly on the home LAN.

The two profiles reuse the same WireGuard peer credentials and should not be active simultaneously.

## Why this design

The Spectrum router does not provide the static-routing flexibility needed for an elegant direct LAN -> AI subnet path while OPNsense remains a secondary router.

A client-side Windows static route was tested but produced unstable SSH sessions. Rather than keep a brittle exception, management was moved fully to WireGuard.

The result is simpler:

- no Windows persistent route
- no direct LAN management dependency
- one proven management boundary
- consistent access control through OPNsense
- home lab remains independent of OPNsense for ordinary LAN traffic

## Design goals

- secure agent execution
- reproducible infrastructure
- default-deny network boundaries
- least-privilege access
- centralized observability and auditability
- separation of agent runtime, tools, data, and secrets
- human approval for sensitive or destructive actions

## Next steps

1. Harden the Debian host.
2. Review and tighten OPNsense egress rules.
3. Add reproducible configuration management.
4. Add container runtime.
5. Add centralized logging and metrics.
6. Define secrets handling.
7. Deploy the first limited-permission agent.

See `docs/` for architecture, networking, management access, troubleshooting history, and decision records.
