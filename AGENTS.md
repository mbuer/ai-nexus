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
- Keep secrets out of Git.

## Current network facts

```text
Home LAN            192.168.1.0/24
Spectrum router     192.168.1.1
OPNsense LAN        192.168.1.25
WireGuard network   10.10.10.0/24
Away laptop peer    10.10.10.3/32
Home laptop peer    10.10.10.4/32
AI network          10.50.0.0/24
OPNsense AI         10.50.0.1
AI Nexus            10.50.0.10
```

AI Nexus has one active network path through the isolated Proxmox bridge `vmbr1`.

IPv6 is intentionally not enabled on the AI segment.

## Management access

Management enters through WireGuard.

### Home

- dedicated peer: `10.10.10.4/32`
- local OPNsense endpoint: `192.168.1.25:51820`
- AllowedIPs: `10.50.0.0/24`

### Away / work

- dedicated peer: `10.10.10.3/32`
- public WireGuard endpoint
- AllowedIPs: `192.168.1.0/24, 10.50.0.0/24`

Do not merge these peers or reuse one peer identity for both profiles.

## Egress

AI Nexus uses OPNsense for DNS, NAT, and controlled Internet access.

Do not broadly enable outbound TCP/22 merely for GitHub.

GitHub SSH is intentionally configured through `ssh.github.com:443`.

## Secrets

Never commit:

- passwords
- API keys
- private SSH keys
- WireGuard private keys
- pre-shared keys
- tokens
- sensitive runtime data

Use placeholders in documentation.

## Change discipline

Before changing networking or firewall behavior:

1. Read `docs/architecture.md`.
2. Read `docs/network.md`.
3. Read `docs/decisions.md`.
4. Check `docs/troubleshooting-2026-09-23.md` before repeating past experiments.
5. Prefer the smallest reversible change.
6. Validate with concrete tests.
7. Update documentation when the architecture or operating procedure changes.

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
