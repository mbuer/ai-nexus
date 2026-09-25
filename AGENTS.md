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

Before changing networking or firewall behavior:

1. Read `docs/architecture.md`.
2. Read `docs/network.md`.
3. Read `docs/decisions.md`.
4. Check `docs/troubleshooting-2026-09-23.md` before repeating past experiments.
5. Prefer the smallest reversible change.
6. Validate with concrete tests.
7. Update documentation when architecture or operating procedures change.

## Troubleshooting guidance

Do not assume a failed ping means routing is broken; ICMP to OPNsense may be intentionally blocked.

Distinguish:

- management ingress
- AI egress
- DNS
- WireGuard
- application behavior

Avoid stacking multiple configuration changes before validating the previous one.

## Repository intent

Future work should move toward:

- Debian hardening
- configuration management
- containerized workloads
- per-agent identities
- secrets handling
- centralized logs and metrics
- versioned agent definitions
- recovery automation

When adding automation, make it understandable and reversible.
