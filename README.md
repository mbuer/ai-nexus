# AI Nexus

Secure, reproducible home-lab platform for running isolated AI agents with controlled access and observability.

## Current status

The base VM and isolated network path are operational.

### VM baseline

- Hypervisor: Proxmox
- VM: `ai-nexus`
- OS: Debian 13.7 (Trixie)
- CPU: 2 vCPU
- RAM: 8 GB
- Disk: 32 GB
- Machine: q35
- Firmware: OVMF / UEFI
- NIC model: VirtIO
- Proxmox firewall: enabled
- QEMU guest agent: installed

Snapshot:

- `baseline-pre-network-segmentation`

### Network

AI Nexus is isolated from the main LAN and uses OPNsense as its only gateway.

- AI subnet: `10.50.0.0/24`
- OPNsense AI interface: `10.50.0.1`
- AI Nexus: `10.50.0.10`
- Proxmox bridge: `vmbr1`
- AI Nexus interface: `ens19`
- IPv6: not used on the AI segment
- Direct LAN NIC: removed

Validated:

- AI Nexus -> OPNsense reachability
- DNS via OPNsense
- HTTPS egress via OPNsense
- Outbound NAT
- Firewall logging
- WireGuard -> AI Nexus SSH
- Remote access from work over WireGuard is stable

### Management access

Remote management:

```text
Laptop / phone
    -> WireGuard
    -> OPNsense
    -> 10.50.0.10:22
```

Local management is currently under investigation. The Windows laptop has a static route:

```text
10.50.0.0/24 via 192.168.1.25
```

This allows SSH to connect, but the local session becomes unstable and resets. Packet captures show retransmissions followed by a TCP reset from the Windows laptop. WireGuard access remains stable.

Potential simplification for the next session: keep the current remote WireGuard profile for away/work use, and test a separate home profile that routes only `10.50.0.0/24` through WireGuard so normal `192.168.1.0/24` lab access stays local.

## Design goals

- Secure agent execution
- Reproducible infrastructure
- Default-deny network boundaries
- Least-privilege access
- Centralized observability and auditability
- Separation of agent runtime, tools, data, and secrets
- Human approval for sensitive or destructive actions

## Next steps

1. Resolve or replace the local static-route management path.
2. Harden the Debian host.
3. Review and tighten OPNsense egress rules.
4. Add reproducible configuration management.
5. Add container runtime.
6. Add centralized logging and metrics.
7. Define secrets handling.
8. Deploy the first limited-permission agent.

See `docs/` for architecture, network state, and decision records.
