# Network Troubleshooting — 2026-09-23/24

## Summary

Two separate management-path problems were investigated:

1. direct LAN routing to the isolated AI subnet
2. an initially unstable Home WireGuard profile

The final working design uses WireGuard for management with separate Home and Away peers.

## Direct-LAN path

The Windows laptop used:

```text
10.50.0.0/24 via 192.168.1.25
```

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
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
```

This avoided the Spectrum router's public-endpoint hairpin behavior and initially worked.

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
Address = 10.10.10.4/32
Keypair = unique Home keypair
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
PersistentKeepalive = 25
```

The original Away peer remained:

```text
Address = 10.10.10.3/32
Keypair = original Away keypair
```

The new Home peer was added separately in OPNsense with the matching Windows public key and `10.10.10.4/32` as its Allowed IP.

## Validation

After reconnecting with the dedicated Home peer:

- AI Nexus showed the SSH source as `10.10.10.4`
- SSH remained stable during active use
- WireGuard handshakes refreshed during active traffic
- normal home-lab traffic remained local
- no Windows static route was required

The evidence strongly suggests that reusing one WireGuard peer identity across the two profiles was the source of the Home tunnel instability.

## GitHub side issue

`git pull` initially appeared to be another network failure.

The Git remote was:

```text
git@github.com:mbuer/ai-nexus.git
```

The AI egress policy allowed HTTP/HTTPS but not generic outbound TCP/22.

GitHub SSH was therefore moved to GitHub's supported TCP/443 endpoint:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

After that, `ssh -T git@github.com` and `git pull` worked without opening outbound TCP/22.

## Final management model

### Home

```text
Windows Home peer 10.10.10.4
    |
WireGuard to 192.168.1.25:51820
    |
OPNsense
    |
AI Nexus 10.50.0.10
```

### Away

```text
Windows Away peer 10.10.10.3
    |
WireGuard to public endpoint
    |
OPNsense
    +-- 192.168.1.0/24
    +-- 10.50.0.0/24
```

## Lessons

1. Do not reuse one WireGuard peer identity for logically separate client profiles when a dedicated peer is easy to create.
2. A technically possible routing workaround may still be a poor operational design.
3. Packet captures prevent random firewall and SSH changes from becoming permanent configuration.
4. Keep troubleshooting-only firewall changes out of the final architecture.
5. Controlled egress can expose legitimate application assumptions, such as Git expecting outbound SSH/22.
6. Prefer narrow exceptions such as GitHub SSH over 443 over broad firewall openings.
