# Management Access

## Purpose

AI Nexus management enters through WireGuard rather than directly from the home LAN.

## Addresses

```text
Home LAN            192.168.1.0/24
OPNsense LAN        192.168.1.25
WireGuard network   10.10.10.0/24
Away laptop peer    10.10.10.3/32
Home laptop peer    10.10.10.4/32
AI network          10.50.0.0/24
AI Nexus            10.50.0.10
SSH                 TCP/22
WireGuard           UDP/51820
```

## Home profile

Use when physically connected to the home LAN.

The Home profile is its own WireGuard peer with a unique keypair.

```ini
[Interface]
Address = 10.10.10.4/32
PrivateKey = <home-private-key>

[Peer]
PublicKey = <OPNsense-instance-public-key>
AllowedIPs = 10.50.0.0/24
Endpoint = 192.168.1.25:51820
PersistentKeepalive = 25
```

The corresponding OPNsense peer uses:

```text
Public Key: <Home Windows public key>
Allowed IPs: 10.10.10.4/32
Instance: HomeWireGuard
Keepalive: 25
```

Never commit WireGuard private keys.

### Expected routes

```text
192.168.1.0/24 -> local Wi-Fi/Ethernet
10.50.0.0/24   -> WireGuard
```

### Test

```powershell
ssh mb@10.50.0.10
```

On AI Nexus:

```bash
who
```

The Home session should show source:

```text
10.10.10.4
```

## Away / work profile

The existing Away profile remains a separate peer.

```ini
[Interface]
Address = 10.10.10.3/32
PrivateKey = <away-private-key>

[Peer]
PublicKey = <OPNsense-instance-public-key>
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
Endpoint = <public-wireguard-endpoint>:51820
```

## Why separate peers

An earlier Home profile reused the same peer identity and tunnel address as the Away profile.

That setup was unstable:

- SSH would work initially
- the session would reset
- new SSH attempts would time out
- restarting the tunnel restored access temporarily

The dedicated Home peer at `10.10.10.4` removed that ambiguity and has remained stable during active use.

Separate peer identities are therefore part of the intended design.

## GitHub access from AI Nexus

The Git remote uses SSH:

```text
git@github.com:mbuer/ai-nexus.git
```

The AI egress policy does not broadly allow outbound TCP/22.

AI Nexus therefore uses:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

Quick validation:

```bash
ssh -T git@github.com
git pull
```

## Windows route state

The old static route is no longer required.

Expected:

```text
Persistent Routes:
None
```

## OPNsense dependency

Management requires:

- WireGuard instance active on OPNsense
- correct Home/Away peer configured
- firewall permission from `10.10.10.0/24` to `10.50.0.10:22`
- AI interface `10.50.0.1/24` available

No direct LAN -> AI SSH rule is required.

## Stability check

A useful Home validation sequence is:

```bash
who
git fetch
curl -4 https://deb.debian.org/ -o /dev/null
```

Watch the Windows WireGuard tunnel during active use.

Expected:

- SSH remains connected
- latest handshake refreshes during active traffic
- transfer counters increase
- session source is `10.10.10.4`

## Quick troubleshooting

### Home SSH times out

Check:

1. Home tunnel is active
2. Home peer has `10.10.10.4/32`
3. endpoint is `192.168.1.25:51820`
4. OPNsense peer contains the matching Home public key
5. OPNsense peer Allowed IPs contains `10.10.10.4/32`

### Session comes from 10.10.10.3

The Away profile is active. The Home profile should appear as `10.10.10.4`.

### Git pull hangs

Verify GitHub SSH is using TCP/443:

```bash
ssh -G github.com | grep -E '^(hostname|port|user) '
```

Expected:

```text
hostname ssh.github.com
port 443
user git
```
