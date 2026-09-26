# AGENTS.md

## Purpose

This repository documents and automates AI Nexus, a security-focused home-lab platform for running isolated AI agents.

Treat the repository as the source of truth for architecture, decisions, and future automation.

## Core principles

- Preserve network isolation by default.
- Prefer least privilege over convenience.
- Prefer explicit, narrow access over broad firewall openings.
- Keep the normal home LAN independent of OPNsense.
- Treat OPNsense as the enforcement point for AI Nexus.
- Do not create direct LAN bypasses around the AI security boundary.
- Prefer reproducible configuration over undocumented manual changes.
- Keep secrets and environment-specific addressing out of Git.

## Public-repository hygiene

This repository is public.

Do not commit:

- exact private IP addresses or subnets from the live environment
- public WAN addresses or dynamic-DNS names
- WireGuard peer addresses
- MAC addresses
- private hostnames that expose the live topology
- VM IDs, backup/job IDs, or other live environment identifiers
- personal or local usernames
- exact environment-specific filesystem paths
- screenshots containing sensitive network details
- passwords, API keys, tokens, private keys, pre-shared keys, or credentials

Use symbolic names in documentation:

```text
HOME_LAN
FIREWALL_LAN
WG_NET
WG_HOME_PEER
WG_AWAY_PEER
AI_NET
AI_GATEWAY
AI_HOST
```

Use `config/network.example.yaml` for safe examples and keep real values in the ignored `config/network.local.yaml`.

## Current architecture

AI Nexus has one active network path through the isolated Proxmox bridge `vmbr1`.

Management enters through WireGuard. Home and Away use separate peer identities.

IPv6 is intentionally not enabled on the AI segment.

## Egress

AI Nexus uses OPNsense for DNS, NAT, firewall policy, and controlled Internet access.

Do not broadly enable outbound TCP/22 merely for GitHub.

GitHub SSH is intentionally configured through `ssh.github.com:443`.

## Change discipline

Before architectural, security, networking, database, ML-integration, or other cross-cutting changes:

1. Read `docs/decisions.md` first and treat recorded decisions as current architectural context unless deliberately superseded by a newer documented decision.
2. Read the relevant architecture and subsystem documentation before proposing changes.
3. For networking or firewall work, read `docs/architecture.md`, `docs/network.md`, and check `docs/troubleshooting-2026-09-23.md` before repeating past experiments.
4. Prefer the smallest reversible change.
5. Validate with concrete tests.
6. Update documentation when architecture or operating procedures change.

## Troubleshooting guidance

Do not assume a failed ping means routing is broken; ICMP to OPNsense may be intentionally blocked.

Distinguish:

- management ingress
- AI egress
- DNS
- WireGuard
- application behavior

Avoid stacking multiple configuration changes before validating the previous one.

## Administrative and recovery invariants

- Routine administration uses a named non-root account.
- Root access is break-glass only and is not the normal SSH path.
- A fresh logical PostgreSQL backup must complete before the Proxmox VM backup proceeds.
- Host hardening, container hardening, and the off-VM recovery chain are implemented and should be preserved unless a deliberate architecture decision replaces them.

## Repository intent

Future work should move toward:

- configuration management
- centralized logs and metrics
- versioned agent definitions
- stronger automated rebuild/recovery workflows

When adding automation, make it understandable and reversible.


## Agent capability pattern

Do not solve a new agent requirement by attaching the agent to a broad network.

Preferred pattern:

- keep the agent on internal Podman networks
- expose a narrowly scoped proxy or service bridge for each external capability
- give datasource credentials the minimum required database privileges
- keep authoritative source data separate from generated analysis and canonical memory
- persist provenance when model output is retained

Current examples:

- OpenAI API through a destination allowlist CONNECT proxy
- BirdNET PostgreSQL through a fixed-destination datasource proxy and read-only database role

## Birdynator development

For normal Birdynator code-only changes, prefer:

```bash
make birdynator-update
```

Use full deploy workflows when proxy/network/runtime infrastructure changes.

Birdynator analyses belong in `analysis_runs`; do not automatically promote model-generated analysis into canonical `memory` without an explicit design decision.
