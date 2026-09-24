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

Management peers:

```text
Away / work laptop   10.10.10.3/32   dedicated keypair
Home laptop          10.10.10.4/32   dedicated keypair
```

SSH to AI Nexus is allowed from:

```text
10.10.10.0/24 -> 10.50.0.10:22
```

The Home and Away profiles are separate peers. Reusing one peer identity for both profiles was tested and produced unstable behavior.

### AI firewall policy

Intended long-term rules include:

- AI network -> This Firewall: DNS TCP/UDP 53
- AI network -> Internet: HTTP/HTTPS egress
- WireGuard subnet -> AI Nexus: SSH TCP 22

Generic outbound SSH from AI Nexus to the Internet is not intentionally allowed.

### GitHub SSH over TCP/443

AI Nexus keeps its GitHub SSH remote but redirects GitHub SSH to GitHub's supported TCP/443 endpoint:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

Validated:

```bash
ssh -T git@github.com
git pull
```

### NAT

OPNsense uses Hybrid Source NAT.

Automatic NAT covers the AI subnet for outbound Internet access.

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

`resolvconf` is installed so DNS is generated persistently from the interface configuration.

## Management access

Direct local LAN management was intentionally abandoned.

### Home profile

```text
Client address = 10.10.10.4/32
Endpoint = 192.168.1.25:51820
AllowedIPs = 10.50.0.0/24
PersistentKeepalive = 25
Keypair = dedicated Home keypair
```

Behavior:

```text
192.168.1.0/24 -> direct home LAN
10.50.0.0/24   -> WireGuard -> OPNsense -> AI
```

### Away / work profile

```text
Client address = 10.10.10.3/32
Endpoint = <public-wireguard-endpoint>:51820
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
Keypair = dedicated Away keypair
```

Behavior:

```text
192.168.1.0/24 -> WireGuard -> home lab
10.50.0.0/24   -> WireGuard -> AI Nexus
```

## Windows route state

No persistent route is required.

With the Home profile active, Windows installs `10.50.0.0/24` through the `10.10.10.4` WireGuard interface.

## Validation

Confirmed:

- DNS through OPNsense
- IPv4 HTTPS egress
- outbound NAT
- remote SSH over WireGuard
- Home SSH via dedicated `10.10.10.4` peer
- Home SSH source observed as `10.10.10.4`
- WireGuard handshakes refresh during active use
- home LAN remains directly reachable with the Home profile active
- no persistent Windows route required
- GitHub SSH over TCP/443
- AI Nexus has no direct LAN NIC

## Cleanup verification

Troubleshooting settings tested during the abandoned direct-LAN path are not part of the intended design:

- per-rule `Disable reply-to`
- global `Disable force gateway`
- direct LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- Windows persistent route
