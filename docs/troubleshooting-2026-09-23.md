# Network Troubleshooting — 2026-09-23

## Summary

The original goal was to manage AI Nexus directly from a Windows laptop on the home LAN while keeping AI Nexus isolated behind OPNsense.

Because OPNsense is not the home's default router, the Spectrum router does not know that `10.50.0.0/24` exists behind `192.168.1.25`.

A Windows static route was therefore tested.

The route allowed SSH to connect but produced unstable sessions. After packet-level troubleshooting, the direct-LAN path was abandoned in favor of a cleaner WireGuard-only management model.

## Original direct-LAN path

```text
Windows laptop
192.168.1.214
    |
static route:
10.50.0.0/24 via 192.168.1.25
    |
OPNsense
    |
AI Nexus
10.50.0.10
```

## Symptom

SSH connected normally and authentication completed.

After a short period the client terminated with:

```text
client_loop: send disconnect: Connection reset
```

## What was ruled out

### Missing basic firewall permission

An explicit LAN rule was added for:

```text
192.168.1.214 -> 10.50.0.10:22
```

The issue remained.

### MTU

Windows successfully sent a DF ping with a 1472-byte payload:

```cmd
ping 10.50.0.10 -f -l 1472
```

This validated a normal 1500-byte IPv4 path.

### OPNsense route table

The route table correctly showed:

```text
192.168.1.0/24 -> directly connected LAN
10.50.0.0/24   -> directly connected AI
default         -> 192.168.1.1
```

### OPNsense ARP

The ARP entry for the laptop matched the laptop's actual MAC address.

### Proxmox Wi-Fi

Proxmox was verified to use physical Ethernet `ents4` for `vmbr0`.

The Wi-Fi interface was down.

### Debian SSH service

The server continued transmitting during the failure.

The final reset came from the Windows client rather than from sshd.

### reply-to / force-gateway experiments

The following were tested:

- per-rule `Disable reply-to`
- global `Disable force gateway`

Neither solved the issue.

They are not required by the final design.

## Packet-capture finding

A tcpdump on AI Nexus showed:

- normal TCP handshake
- normal SSH negotiation
- successful login
- retransmissions
- client acknowledgements no longer advancing for some server data
- eventual TCP RST from `192.168.1.214`

The important conclusion was not that Windows itself was necessarily defective, but that the direct routed path was behaving unreliably enough to be a poor management foundation.

## Why the issue was not pursued further

The goal was secure, reliable management—not proving every detail of an awkward secondary-router edge case.

Continuing would have added more:

- client-specific routes
- special firewall behavior
- Spectrum-router dependencies
- troubleshooting-only exceptions
- operational knowledge required to maintain the path

WireGuard was already stable remotely, so the better engineering decision was to reuse the proven management boundary.

## Final solution

### Home

```text
Windows
    |
WireGuard
Endpoint 192.168.1.25:51820
AllowedIPs 10.50.0.0/24
    |
OPNsense
    |
AI Nexus
```

### Away

```text
Windows
    |
WireGuard
Endpoint public:51820
AllowedIPs 192.168.1.0/24, 10.50.0.0/24
    |
OPNsense
    +-- home lab
    +-- AI Nexus
```

## Cleanup performed

- Windows persistent `10.50.0.0/24 via 192.168.1.25` route removed
- Home WireGuard profile created
- remote WireGuard profile retained
- temporary direct-LAN design rejected
- AI DNS made persistent through `resolvconf`
- IPv4 DNS and HTTPS egress validated
- recovery snapshot taken after cleanup

## Lessons

1. A secondary router behind a consumer gateway can provide useful segmentation, but management routing can become awkward when the primary router does not support static routes.
2. A technically possible path is not automatically a good operational design.
3. Packet captures were useful because they prevented random SSH/firewall changes from continuing indefinitely.
4. WireGuard provides a cleaner management boundary than per-client static routing in this topology.
5. Separate Home and Away profiles make split routing explicit and easy to reason about.
6. The normal home network remains independent of OPNsense, which preserves the original architectural goal.
