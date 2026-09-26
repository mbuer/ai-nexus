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

## Rootless runtime audit coverage

The AI Nexus rootless runtime is covered by targeted auditd watches in addition to the host-level security watches.

Verified watches:

- `/home/mb/.config/containers/systemd/` with key `ai_nexus_quadlet`
- `/home/mb/projects/ai-nexus/config/runtime.local.env` with key `ai_nexus_runtime`
- `/home/mb/ai-nexus-runtime/secrets/` with key `ai_nexus_secrets`

The Quadlet directory is mode `0700`, the local runtime configuration is mode `0600`, the secrets directory is mode `0700`, and the individual secret source files are mode `0600`.

Audit attribution was verified by creating and deleting a temporary file in the Quadlet directory. auditd recorded both events with the `ai_nexus_quadlet` key and attributed them to the logged-in `mb` user rather than only to a privileged helper process.

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

## Supporting-service hardening

The OpenAI egress proxy has been verified with the same containment profile used for the agent where compatible:

- unprivileged application user
- read-only root filesystem
- no host ports
- empty effective, permitted, and bounding Linux capability sets
- `no-new-privileges` active
- seccomp filtering active
- private IPC namespace
- no attachment to the agent-memory PostgreSQL network
- outbound TLS reachability retained only through its dedicated egress network and application allowlist

The BirdNET proxy is also verified with the compatible containment profile:

- unprivileged application user
- read-only root filesystem
- no host ports
- empty effective, permitted, and bounding Linux capability sets
- `no-new-privileges` active
- seccomp filtering active
- private IPC namespace
- no attachment to the agent-memory PostgreSQL network
- fixed-destination PostgreSQL reachability retained through its dedicated egress network

The embedding service is also verified with the compatible containment profile:

- unprivileged application user
- read-only root filesystem
- no host ports
- empty effective, permitted, and bounding Linux capability sets
- `no-new-privileges` active
- seccomp filtering active
- private IPC namespace
- local model remains pinned and offline
- text-to-vector smoke test passes at 384 dimensions

## PostgreSQL hardening

PostgreSQL retains a writable root filesystem and its normal image entrypoint intentionally so initialization, upgrades, and recovery behavior are not disrupted.

Verified controls for the database runtime:

- rootless Podman lifecycle
- PostgreSQL server process runs as UID/GID 999
- data directory remains mode `0700` and owned by UID/GID 999
- no host port is published
- internal container network only
- `no-new-privileges` active
- seccomp filtering active
- private IPC namespace
- superuser password secret mounted root-only with mode `0400`
- database ownership and Birdynator runtime-role separation remain enforced

These controls were verified after a PostgreSQL restart, migration check, full runtime verification, and fresh logical backup. The writable root filesystem and root-capable image entrypoint are retained deliberately rather than forcing a more aggressive profile that could interfere with PostgreSQL initialization or recovery.

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
