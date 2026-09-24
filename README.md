# AI Nexus

Secure, reproducible home-lab platform for running isolated AI agents with controlled access and observability.

## Current status

The base VM is installed and the isolated AI network path has been validated.

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

A snapshot was created before network segmentation: `baseline-pre-network-segmentation`.

### Network progress

- Existing LAN path remains temporarily available on `ens18`.
- A dedicated internal Proxmox bridge, `vmbr1`, was created for the AI segment.
- OPNsense received a dedicated AI interface on `vtnet1`.
- AI gateway: `10.50.0.1/24`
- `ai-nexus` test address on `ens19`: `10.50.0.10/24`
- An explicit ICMP rule allows the AI subnet to reach the OPNsense firewall for testing.
- Connectivity from `ai-nexus` to `10.50.0.1` is confirmed.

## Design goals

- Secure agent execution
- Reproducible infrastructure
- Default-deny network boundaries
- Least-privilege access
- Centralized observability and auditability
- Clear separation between agent runtime, tools, data, and secrets
- Human approval for sensitive or destructive actions

## Next steps

1. Make the AI interface configuration persistent.
2. Define controlled DNS and Internet egress through OPNsense.
3. Verify routing and logging.
4. Remove the temporary direct LAN path from `ai-nexus`.
5. Add WireGuard access into the AI subnet.
6. Harden the base OS.
7. Add configuration management.
8. Add the container runtime and first limited-permission agent.

See `docs/` for architecture, network state, and decision records.
