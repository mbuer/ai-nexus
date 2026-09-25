# Network

## Topology

```text
Internet
   |
Home router
   |
HOME_LAN
   |
OPNsense
   +-- WG_NET
   |
AI_GATEWAY
   |
vmbr1
   |
AI_HOST
```

Exact live addressing is intentionally kept out of this public repository.

## Design intent

The normal home network remains independent of OPNsense.

The AI segment intentionally depends on OPNsense so AI Nexus has one controlled routing, firewall, NAT, DNS, and logging boundary.

If OPNsense is unavailable:

- normal home LAN operation continues
- AI Nexus loses routed connectivity
- WireGuard management of AI Nexus is unavailable

## Proxmox

### Main LAN

`vmbr0` is bridged to the physical LAN interface.

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

OPNsense is attached to `HOME_LAN` and uses the home router as its upstream gateway.

### AI interface

- dedicated interface for `AI_NET`
- IPv4 static
- IPv6 disabled
- gateway: none
- private network blocking: disabled
- bogon blocking: disabled

### WireGuard

Management uses `WG_NET`.

Home and Away use separate dedicated peer identities.

SSH to AI Nexus is allowed conceptually as:

```text
WG_NET -> AI_HOST:22
```

### AI firewall policy

Intended long-term rules include:

- AI network -> OPNsense: DNS TCP/UDP 53
- AI network -> Internet: HTTP/HTTPS egress
- WireGuard network -> AI Nexus: SSH TCP 22

Generic outbound SSH from AI Nexus to the Internet is not intentionally allowed.

### GitHub SSH over TCP/443

AI Nexus redirects GitHub SSH to GitHub's supported TCP/443 endpoint:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

### NAT

OPNsense uses Hybrid Source NAT.

Automatic outbound NAT covers `AI_NET` for Internet access.

## AI Nexus

Persistent interface configuration conceptually contains:

```text
address <AI_HOST>/<PREFIX>
gateway <AI_GATEWAY>
dns-nameservers <AI_GATEWAY>
```

The previous direct LAN NIC was removed after the isolated path and WireGuard management path were validated.

Normal IPv4 traffic follows:

```text
AI_HOST
    -> AI_GATEWAY
    -> OPNsense policy
    -> NAT
    -> Internet
```

## DNS

AI Nexus uses OPNsense as its resolver.

`resolvconf` is installed so DNS is generated persistently from the interface configuration.

## Management access

Direct local LAN management was intentionally abandoned.

### Home profile

```text
Client = dedicated Home peer
Endpoint = local OPNsense LAN address
AllowedIPs = AI_NET
PersistentKeepalive = 25
```

Behavior:

```text
HOME_LAN -> direct home LAN
AI_NET   -> WireGuard -> OPNsense -> AI
```

### Away / work profile

```text
Client = dedicated Away peer
Endpoint = public WireGuard endpoint
AllowedIPs = HOME_LAN, AI_NET
```

Behavior:

```text
HOME_LAN -> WireGuard -> home lab
AI_NET   -> WireGuard -> AI Nexus
```

## Windows route state

No persistent route is required.

When the Home profile is active, Windows installs the AI-subnet route through the Home WireGuard interface.

## Validation

Confirmed:

- DNS through OPNsense
- IPv4 HTTPS egress
- outbound NAT
- remote SSH over WireGuard
- Home SSH via a dedicated peer
- WireGuard handshakes refresh during active use
- home LAN remains directly reachable with the Home profile active
- no persistent Windows route required
- GitHub SSH over TCP/443
- AI Nexus has no direct LAN NIC

## Public configuration pattern

Safe example values live in:

```text
config/network.example.yaml
```

Real values belong in:

```text
config/network.local.yaml
```

The local file is ignored by Git.

## Cleanup verification

Troubleshooting settings tested during the abandoned direct-LAN path are not part of the intended design:

- per-rule `Disable reply-to`
- global `Disable force gateway`
- direct LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- Windows persistent route


## Application-specific egress

Host-level outbound policy remains simple, but agent capabilities are narrowed at the container/service layer.

### OpenAI

Birdynator does not receive direct general Internet access.

```text
Birdynator -> OpenAI CONNECT proxy -> api.openai.com:443
```

The proxy is the only component on the Birdynator path with Internet egress.

### BirdNET datasource

Birdynator does not receive general LAN access simply to read BirdNET.

```text
Birdynator -> BirdNET fixed-destination proxy -> BIRDNET_DB_HOST:5432
```

The upstream OPNsense policy permits only the intended AI-host-to-datasource PostgreSQL path, and PostgreSQL separately enforces the dedicated read-only login.

Live addresses remain in ignored local configuration and are not documented here.
