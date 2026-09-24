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

Known recovery snapshots:

- `baseline-pre-network-segmentation`
- post-network-cleanup snapshot taken after the isolated network and WireGuard management path were stabilized

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
- stable home SSH over a dedicated WireGuard peer
- normal home-lab access remains local while the Home profile is active
- Windows static route workaround removed
- GitHub SSH works over TCP/443 without opening generic outbound TCP/22

### Management access

AI Nexus management uses WireGuard both at home and away.

#### Away / work peer

- client address: `10.10.10.3/32`
- existing dedicated keypair
- endpoint: public WireGuard endpoint
- AllowedIPs:
  - `192.168.1.0/24`
  - `10.50.0.0/24`

#### Home peer

- client address: `10.10.10.4/32`
- separate dedicated keypair
- endpoint: `192.168.1.25:51820`
- AllowedIPs:
  - `10.50.0.0/24`

Normal `192.168.1.0/24` traffic stays directly on the home LAN.

The Home and Away profiles are separate WireGuard peers and do not share client identity.

## Controlled GitHub access

The repository remote uses SSH, but generic outbound TCP/22 is intentionally not opened from the AI subnet.

AI Nexus therefore uses GitHub's supported SSH-over-443 endpoint via `~/.ssh/config`:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

This preserves SSH-key authentication while keeping the outbound policy limited to the existing HTTPS/443 path.

## Why this design

The Spectrum router does not provide the static-routing flexibility needed for an elegant direct LAN -> AI subnet path while OPNsense remains a secondary router.

A client-side Windows static route was tested but produced unstable SSH sessions. Reusing the same WireGuard peer identity for both Home and Away profiles also produced instability.

The final management design uses separate WireGuard peers.

The result is simpler and more deterministic:

- no Windows persistent route
- no direct LAN management dependency
- unique peer identity per Home/Away profile
- consistent access control through OPNsense
- home lab remains independent of OPNsense for ordinary LAN traffic
- GitHub access works without broadly allowing outbound SSH

## Design goals

- secure agent execution
- reproducible infrastructure
- default-deny network boundaries
- least-privilege access
- centralized observability and auditability
- separation of agent runtime, tools, data, and secrets
- human approval for sensitive or destructive actions

## Next steps

1. Continue observing Home WireGuard stability under normal use.
2. Harden the Debian host.
3. Review and tighten OPNsense egress rules.
4. Add reproducible configuration management.
5. Add container runtime.
6. Add centralized logging and metrics.
7. Define secrets handling.
8. Deploy the first limited-permission agent.

See `docs/` for architecture, networking, management access, troubleshooting history, and decision records.
