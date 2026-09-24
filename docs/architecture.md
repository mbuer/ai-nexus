# Architecture

## Purpose

AI Nexus is a home-lab execution platform for AI agents. The design prioritizes containment, reproducibility, explicit permissions, and independent observability.

## Principles

- Agents request capabilities; the platform grants and enforces them.
- The agent runtime does not implicitly trust the surrounding LAN.
- Read and write capabilities should be separated.
- Sensitive actions should require explicit approval.
- Secrets must remain outside source control.
- Workloads should be disposable where practical; persistent state should be separated.
- Audit data should eventually leave the agent VM so the agent cannot erase the only record of its actions.

## Current platform

```text
Home LAN / Internet
        |
     OPNsense
   192.168.1.25
        |
        +-- WireGuard management
        |
     AI interface
     10.50.0.1/24
        |
      vmbr1
        |
     ai-nexus
     10.50.0.10
```

### ai-nexus

- Debian 13.7
- 2 vCPU
- 8 GB RAM
- 32 GB disk
- q35 + OVMF / UEFI
- VirtIO networking
- single active network path through `vmbr1`

The previous direct LAN NIC has been removed.

## Security boundary

OPNsense is the enforcement point between AI Nexus and the rest of the network.

This creates a deliberate asymmetry:

- The AI segment depends on OPNsense.
- The normal home network does not depend on OPNsense.

If OPNsense is unavailable, AI Nexus loses routed connectivity, but the rest of the home network continues to operate.

## Management model

WireGuard is the proven management path and is stable from remote networks.

The direct local-LAN path using a client-side static route is currently under investigation because SSH sessions reset after establishing successfully.

This is treated as a management-path usability issue rather than a failure of the isolation architecture.

The preferred simplification to test next is a dedicated home WireGuard profile that routes only `10.50.0.0/24`, leaving the normal `192.168.1.0/24` home-lab network local.

## Planned platform layers

1. Proxmox VM boundary
2. OPNsense network enforcement
3. Hardened Debian host
4. Containerized workloads
5. Per-agent identities and permissions
6. Secrets management
7. Centralized logging and metrics
8. Versioned agent definitions and infrastructure configuration
