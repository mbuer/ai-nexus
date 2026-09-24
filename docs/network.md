# Network

## Topology

```text
Internet
   |
Spectrum router
192.168.1.1
   |
Home LAN 192.168.1.0/24
   |
OPNsense 192.168.1.25
   |
AI 10.50.0.1/24
   |
vmbr1
   |
ai-nexus 10.50.0.10/24
```

## Proxmox

`vmbr0` is bridged to the physical Ethernet interface `ents4`.

`vmbr1` is an internal Linux bridge used only for the isolated AI segment.

- No physical bridge port
- No Proxmox host IP
- OPNsense AI interface attached
- AI Nexus attached

The Proxmox Wi-Fi interface is down and is not part of this path.

## OPNsense

### AI interface

- Device: `vtnet1`
- Address: `10.50.0.1/24`
- IPv4: static
- IPv6: disabled
- Gateway: none
- Private network blocking: disabled
- Bogon blocking: disabled

### Firewall policy

Current explicit rules include:

- AI network -> This Firewall: ICMP for diagnostics
- AI network -> This Firewall: DNS TCP/UDP 53
- AI network -> Internet: HTTP/HTTPS egress
- WireGuard subnet `10.10.10.0/24` -> `10.50.0.10:22`: SSH
- Local management host `192.168.1.214` -> `10.50.0.10:22`: SSH

Pass-rule logging is enabled during validation.

### NAT

OPNsense uses Hybrid Source NAT.

Automatic rules include the AI network, translating `10.50.0.0/24` to the OPNsense LAN address for outbound Internet access.

The existing manual WireGuard NAT rule remains unchanged.

## AI Nexus

Persistent Debian configuration:

```text
auto ens19
iface ens19 inet static
    address 10.50.0.10/24
    gateway 10.50.0.1
```

System DNS was corrected to use OPNsense:

```text
nameserver 10.50.0.1
```

The previous main-LAN NIC was removed after the isolated path and WireGuard management path were validated.

Normal IPv4 traffic now exits through:

```text
10.50.0.10
    -> 10.50.0.1
    -> OPNsense policy
    -> NAT
    -> Internet
```

## Management access

### Remote

WireGuard clients include `10.50.0.0/24` in AllowedIPs.

SSH is explicitly permitted from:

```text
10.10.10.0/24 -> 10.50.0.10:22
```

Remote SSH from work has been stable.

ICMP from WireGuard remains blocked by default, so ping/traceroute may fail even when SSH works.

### Local laptop

The Spectrum router does not provide a route to `10.50.0.0/24`, so the Windows laptop currently uses:

```text
10.50.0.0/24 via 192.168.1.25
```

Persistent Windows route:

```cmd
route -p add 10.50.0.0 mask 255.255.255.0 192.168.1.25 metric 1
```

Remove it with:

```cmd
route delete 10.50.0.0 mask 255.255.255.0 192.168.1.25
```

This path is currently unstable: SSH connects, exchanges traffic, then resets.

## Troubleshooting checkpoint — 2026-09-23

Confirmed:

- DNS via `10.50.0.1`
- HTTPS egress through OPNsense
- outbound NAT
- remote SSH over WireGuard
- MTU test with 1472-byte ICMP payload + DF succeeds, confirming a 1500-byte path
- OPNsense routing table is correct:
  - `192.168.1.0/24` directly connected on LAN
  - `10.50.0.0/24` directly connected on AI
- OPNsense ARP for `192.168.1.214` matches the laptop MAC
- Proxmox LAN bridge uses physical Ethernet `ents4`, not Wi-Fi
- per-rule `Disable reply-to` did not fix local SSH
- global `Disable force gateway` did not fix local SSH

Packet captures show:

- SSH establishes successfully
- Debian continues transmitting
- repeated TCP retransmissions occur
- Windows eventually sends the TCP RST

Do not treat the local static-route path as production-ready yet.

### Next diagnostic / design option

Prefer a simplification over additional one-off routing tweaks:

- keep the existing away/work WireGuard profile, which is already stable
- test a separate home WireGuard profile with only:
  - `10.50.0.0/24`

This would keep normal `192.168.1.0/24` lab access local while routing only AI Nexus management through WireGuard.
