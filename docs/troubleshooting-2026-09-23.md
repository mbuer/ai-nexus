# Network Troubleshooting — 2026-09-23/24

## Summary

Two separate management-path problems were investigated:

1. direct LAN routing to the isolated AI subnet
2. an initially unstable Home WireGuard profile

The final working design uses WireGuard for management with separate Home and Away peers.

Exact live addresses have been removed from this public troubleshooting record.

## Direct-LAN path

A Windows client-side static route to `AI_NET` through the OPNsense LAN address was tested.

SSH connected but later reset.

Testing ruled out:

- missing firewall permission
- normal MTU failure
- incorrect OPNsense routes
- incorrect OPNsense ARP
- Proxmox Wi-Fi bridging
- sshd itself as the reset source
- simple `reply-to` or force-gateway fixes

A packet capture showed retransmissions followed by a TCP RST from the Windows client.

The static-route approach was abandoned.

## First Home WireGuard design

A Home client profile was created by reusing the same WireGuard peer identity and address as the existing Away profile.

Home routing was:

```text
Endpoint = local OPNsense LAN address
AllowedIPs = AI_NET
```

This avoided public-endpoint hairpin behavior and initially worked.

However, it later showed a repeating failure pattern:

```text
SSH works
-> connection resets
-> new SSH attempts time out
-> restarting WireGuard restores access temporarily
```

## Dedicated Home peer

A new Home peer was created with:

```text
Address = dedicated WG_HOME_PEER
Keypair = unique Home keypair
Endpoint = local OPNsense LAN address
AllowedIPs = AI_NET
PersistentKeepalive = 25
```

The Away profile retained its own dedicated peer identity and keypair.

## Validation

After reconnecting with the dedicated Home peer:

- AI Nexus showed the dedicated Home peer as the SSH source
- SSH remained stable during active use
- WireGuard handshakes refreshed during active traffic
- normal home-lab traffic remained local
- no Windows static route was required

The evidence strongly suggests that reusing one WireGuard peer identity across the two profiles was the source of the Home tunnel instability.

## GitHub side issue

`git pull` initially appeared to be another network failure.

The AI egress policy allowed HTTP/HTTPS but not generic outbound TCP/22.

GitHub SSH was therefore moved to GitHub's supported TCP/443 endpoint:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

After that, GitHub SSH and `git pull` worked without opening outbound TCP/22.

## Final management model

### Home

```text
Windows Home peer
    |
WireGuard to local OPNsense endpoint
    |
OPNsense
    |
AI_HOST
```

### Away

```text
Windows Away peer
    |
WireGuard to public endpoint
    |
OPNsense
    +-- HOME_LAN
    +-- AI_NET
```

## Lessons

1. Do not reuse one WireGuard peer identity for logically separate client profiles when a dedicated peer is easy to create.
2. A technically possible routing workaround may still be a poor operational design.
3. Packet captures prevent random firewall and SSH changes from becoming permanent configuration.
4. Keep troubleshooting-only firewall changes out of the final architecture.
5. Controlled egress can expose legitimate application assumptions, such as Git expecting outbound SSH/22.
6. Prefer narrow exceptions such as GitHub SSH over 443 over broad firewall openings.
7. Public documentation can preserve the architecture without publishing the live environment's exact addressing.
