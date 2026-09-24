# AI Nexus

Secure, reproducible home-lab platform for running isolated AI agents with controlled access and observability.

## Goals

- Secure agent execution
- Reproducible infrastructure
- Controlled network access
- Centralized observability
- Least-privilege permissions
- Clear separation between agent runtime, tools, data, and secrets

## Current VM Baseline

- Hypervisor: Proxmox
- VM name: `ai-nexus`
- OS: Debian 13
- CPU: 2 vCPU
- RAM: 8 GB
- Disk: 32 GB
- Machine type: q35
- Firmware: OVMF / UEFI
- Network: VirtIO on `vmbr0`
- Proxmox firewall: enabled
- Current LAN access is temporary pending network segmentation

## Planned Architecture

1. Harden base OS
2. Define network and firewall boundaries
3. Add reproducible configuration management
4. Add container runtime
5. Add centralized logging and monitoring
6. Deploy first limited-permission agent
