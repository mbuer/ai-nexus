# Security Baseline

## Scope

This document records the current Debian host hardening baseline for AI Nexus.

OPNsense remains the primary network-policy and egress enforcement point. The host controls below provide defense in depth without duplicating every upstream rule.

## SSH

Current policy:

- direct root SSH disabled with `PermitRootLogin no`
- public-key authentication enabled
- password authentication intentionally retained for the non-root admin account
- management SSH is reachable only through the WireGuard management network

The password fallback is deliberate for the current build phase and can be revisited later.

## nftables

The host firewall is enabled persistently.

Policy:

```text
input:   default drop
forward: default drop
output:  accept
```

Allowed inbound traffic:

- loopback
- established/related connections
- SSH from the WireGuard management network
- ICMP and ICMPv6 for diagnostics

Outbound filtering remains primarily an OPNsense responsibility. This keeps the host policy small and understandable while preserving centralized egress logging and enforcement.

## Automatic updates

`unattended-upgrades` is enabled.

Current behavior:

- package lists refreshed daily
- unattended upgrades run daily
- current Debian release packages are eligible
- Debian security packages are eligible
- proposed updates and backports are not enabled automatically
- automatic reboot is disabled

Reboots remain deliberate maintenance actions.

## Logging

Persistent systemd journal storage is enabled under `/var/log/journal`.

This preserves host logs across reboots.

## Audit

`auditd` and `audispd-plugins` are enabled.

Targeted watches cover:

- SSH configuration
- sudoers configuration
- nftables configuration
- local user/group identity files
- systemd unit configuration

A test change under `/etc/systemd/system` was successfully recorded with the expected audit key and acting user attribution.

The rules are intentionally small rather than adopting a broad generic compliance profile.

## Agent container hardening

Birdynator is deployed as a rootless Podman container and is additionally constrained at runtime.

Verified controls:

- container process runs as an unprivileged application user
- root filesystem is read-only
- no host ports are published
- no host devices are passed through
- PID namespace is private
- IPC namespace is private
- seccomp filtering is active
- effective, permitted, and bounding Linux capability sets are empty
- `no-new-privileges` is active
- mounted Birdynator secrets are restricted to UID/GID 10001 with mode `0400`
- rootless user-namespace mapping is verified; container root maps to the non-root host user and container UIDs map into the subordinate UID range
- direct Internet access from the agent is blocked
- OpenAI access is available only through the dedicated allowlist proxy
- BirdNET datasource access is available only through the dedicated database proxy
- BirdNET datasource sessions are verified read-only

The verification script checks these properties after deployment so a runtime drift or failed hardening change causes verification to fail rather than being silently accepted.

## Deployment verification

The Birdynator update workflow installs the current Quadlet definition into the user systemd container directory before reloading systemd and restarting the service. This prevents a code/image update from accidentally leaving an older runtime policy active.

Proxy image builds use the cached pinned Python base image by default. Set `PROXY_REFRESH_BASE=1` when an intentional base-image refresh is required.

## Recovery checkpoint

Snapshot:

```text
baseline-security-audit
```

Description:

```text
Hardened Debian baseline with root SSH disabled, nftables host firewall, unattended upgrades, persistent journald, and targeted auditd rules verified.
```

This snapshot marks the end of the initial OS/security baseline before the agent runtime and container layers are added.
