# Architecture

## Purpose

AI Nexus is a home-lab execution platform for AI agents. The platform is designed around containment, reproducibility, explicit permissions, and independent observability.

## Principles

- Agents request capabilities; the platform grants and enforces them.
- The agent runtime should not implicitly trust the surrounding LAN.
- Read and write capabilities should be separated.
- Sensitive actions should require explicit approval.
- Secrets must remain outside source control.
- Workloads should be disposable where possible; persistent state should be separated.
- Logs and audit records should eventually leave the agent VM so the agent cannot erase the only record of its actions.

## Current platform

```text
Proxmox
├── OPNsense
│   ├── existing home-lab interface
│   └── AI interface: 10.50.0.1/24
│
└── ai-nexus
    ├── Debian 13.7
    ├── 2 vCPU
    ├── 8 GB RAM
    ├── 32 GB disk
    ├── ens18: temporary main-LAN path
    └── ens19: isolated AI path via vmbr1
```

The AI segment is intentionally dependent on OPNsense while the normal home network is not. This allows OPNsense to become the enforcement and logging point for agent traffic without making the home network dependent on the firewall VM.

## Planned platform layers

1. Proxmox VM boundary
2. OPNsense network enforcement
3. Hardened Debian host
4. Containerized workloads
5. Per-agent identities and permissions
6. Secrets management
7. Centralized logging and metrics
8. Versioned agent definitions and infrastructure configuration
