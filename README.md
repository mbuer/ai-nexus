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
- Local laptop -> AI Nexus SSH through OPNsense

### Management access

Remote management:

```text
Laptop / phone
    -> WireGuard
    -> OPNsense
    -> 10.50.0.10:22
```

Local management:

```text
Laptop
    -> static route for 10.50.0.0/24
    -> 192.168.1.25 (OPNsense)
    -> 10.50.0.10
```

The Windows static route is required because the Spectrum router does not provide the route to the isolated AI subnet.

## Design goals

- Secure agent execution
- Reproducible infrastructure
- Default-deny network boundaries
- Least-privilege access
- Centralized observability and auditability
- Separation of agent runtime, tools, data, and secrets
- Human approval for sensitive or destructive actions

## Next steps

1. Harden the Debian host.
2. Review and tighten OPNsense egress rules.
3. Add reproducible configuration management.
4. Add container runtime.
5. Add centralized logging and metrics.
6. Define secrets handling.
7. Deploy the first limited-permission agent.

See `docs/` for architecture, network state, and decision records.
