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
   +-- WireGuard 10.10.10.0/24
   |
AI interface 10.50.0.1/24
   |
vmbr1
   |
ai-nexus 10.50.0.10/24
```

## Design intent

The normal home network remains independent of OPNsense.

The AI segment intentionally depends on OPNsense so AI Nexus has one controlled routing, firewall, NAT, DNS, and logging boundary.

If OPNsense is unavailable:

- normal home LAN operation continues
- AI Nexus loses routed connectivity
- WireGuard management of AI Nexus is unavailable

This is intentional.

## Proxmox

### Main LAN

`vmbr0` is bridged to physical Ethernet interface `ents4`.

The Proxmox Wi-Fi interface is down and is not part of the production path.

### AI bridge

`vmbr1` is an internal Linux bridge used only for the isolated AI network.

Properties:

- no physical bridge port
- no Proxmox host IP
- OPNsense AI NIC attached
- AI Nexus NIC attached
- no direct Layer-3 path from the Proxmox host into the AI subnet

## OPNsense

### LAN side

- LAN address: `192.168.1.25/24`
- upstream/default gateway: Spectrum router `192.168.1.1`

### AI interface

- device: `vtnet1`
- address: `10.50.0.1/24`
- IPv4: static
- IPv6: disabled
- gateway: none
- private network blocking: disabled
- bogon blocking: disabled

### WireGuard

WireGuard network:

```text
10.10.10.0/24
```

SSH to AI Nexus is allowed from:

```text
10.10.10.0/24 -> 10.50.0.10:22
```

### AI firewall policy

Intended long-term rules include:

- AI network -> This Firewall: DNS TCP/UDP 53
- AI network -> Internet: HTTP/HTTPS egress
- WireGuard subnet -> AI Nexus: SSH TCP 22

Generic outbound SSH from AI Nexus to the Internet is not intentionally allowed.

This is why a normal GitHub SSH remote on TCP/22 times out even though inbound management SSH works correctly.

### GitHub SSH over TCP/443

AI Nexus keeps its GitHub SSH remote but redirects GitHub SSH to GitHub's supported TCP/443 endpoint:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

This allows:

```text
git@github.com:mbuer/ai-nexus.git
```

to continue using the existing SSH key without adding a broad outbound TCP/22 firewall rule.

Validated:

```bash
ssh -T git@github.com
git pull
```

### NAT

OPNsense uses Hybrid Source NAT.

Automatic NAT covers the AI subnet for outbound Internet access.

The existing WireGuard NAT configuration remains separate and unchanged.

## AI Nexus

Persistent interface configuration:

```text
auto ens19
iface ens19 inet static
    address 10.50.0.10/24
    gateway 10.50.0.1
    dns-nameservers 10.50.0.1
```

The previous direct LAN NIC was removed after the isolated path and WireGuard management path were validated.

Normal IPv4 traffic follows:

```text
10.50.0.10
    -> 10.50.0.1
    -> OPNsense policy
    -> NAT
    -> Internet
```

## DNS

AI Nexus uses OPNsense as its resolver:

```text
10.50.0.1
```

`resolvconf` is installed so the DNS server is generated persistently from the interface configuration rather than maintained by hand in `/etc/resolv.conf`.

Validated:

```text
/etc/resolv.conf
nameserver 10.50.0.1
```

IPv4 name resolution and HTTPS egress were tested successfully against `deb.debian.org`.

## Management access

Direct local LAN management was intentionally abandoned.

The working model is WireGuard for both home and remote management.

### Home profile

```text
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
```

Behavior:

```text
192.168.1.0/24 -> direct home LAN
10.50.0.0/24   -> WireGuard -> OPNsense -> AI
```

### Away / work profile

```text
Endpoint = <public-wireguard-endpoint>:51820
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
```

Behavior:

```text
192.168.1.0/24 -> WireGuard -> home lab
10.50.0.0/24   -> WireGuard -> AI Nexus
```

The same WireGuard peer credentials are reused across the two client profiles. Only one profile should be active at a time.

## Windows route state

The previous persistent route:

```text
10.50.0.0/24 via 192.168.1.25
```

was removed.

Current intended state:

```text
Persistent Routes:
None
```

When the Home WireGuard profile is active, Windows installs:

```text
10.50.0.0/24 -> On-link via WireGuard client address
```

## Validation

Confirmed:

- `10.50.0.10 -> 10.50.0.1`
- DNS through OPNsense
- IPv4 HTTPS egress
- outbound NAT
- remote SSH over WireGuard
- home SSH over WireGuard
- home LAN remains directly reachable with the Home profile active
- no persistent Windows route required
- GitHub SSH over TCP/443
- AI Nexus has no direct LAN NIC
- IPv6 cannot bypass the AI firewall because it is not enabled on the AI segment

## Cleanup verification

Troubleshooting settings tested during the abandoned direct-LAN path are not part of the intended design:

- per-rule `Disable reply-to`
- global `Disable force gateway`
- direct LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- Windows persistent route

Verify after any future restore that these have not accidentally reappeared.
