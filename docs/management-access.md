# Management Access

## Purpose

AI Nexus management enters through WireGuard rather than directly from the home LAN.

This public document intentionally omits live environment addresses.

## Symbolic addresses

```text
HOME_LAN
FIREWALL_LAN
WG_NET
WG_HOME_PEER
WG_AWAY_PEER
AI_NET
AI_HOST
```

## Home profile

Use when physically connected to the home LAN.

The Home profile is its own WireGuard peer with a unique keypair.

```ini
[Interface]
Address = <WG_HOME_PEER>
PrivateKey = <home-private-key>

[Peer]
PublicKey = <OPNsense-instance-public-key>
AllowedIPs = <AI_NET>
Endpoint = <FIREWALL_LAN>:51820
PersistentKeepalive = 25
```

The corresponding OPNsense peer uses the Home client's public key and matching Home peer address.

Never commit WireGuard private keys or live peer addresses to this public repository.

### Expected routes

```text
HOME_LAN -> local Wi-Fi/Ethernet
AI_NET   -> WireGuard
```

### Test

```powershell
ssh mb@<AI_HOST>
```

On AI Nexus:

```bash
who
```

The session should show the dedicated Home WireGuard peer as the source.

## Away / work profile

The Away profile remains a separate peer.

```ini
[Interface]
Address = <WG_AWAY_PEER>
PrivateKey = <away-private-key>

[Peer]
PublicKey = <OPNsense-instance-public-key>
AllowedIPs = <HOME_LAN>, <AI_NET>
Endpoint = <public-wireguard-endpoint>:51820
```

## Why separate peers

An earlier Home profile reused the same peer identity and tunnel address as the Away profile.

That setup was unstable:

- SSH would work initially
- the session would reset
- new SSH attempts would time out
- restarting the tunnel restored access temporarily

A dedicated Home peer removed that ambiguity and remained stable during active use.

## GitHub access from AI Nexus

The Git remote uses SSH, while the AI egress policy does not broadly allow outbound TCP/22.

AI Nexus therefore uses:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

## Windows route state

The old static-route workaround is no longer required.

Expected:

```text
Persistent Routes:
None
```

## OPNsense dependency

Management requires:

- WireGuard active on OPNsense
- correct Home/Away peer configured
- firewall permission from `WG_NET` to `AI_HOST:22`
- AI gateway available

No direct LAN -> AI SSH rule is required.

## Stability check

A useful Home validation sequence is:

```bash
who
git fetch
curl -4 https://deb.debian.org/ -o /dev/null
```

Expected:

- SSH remains connected
- latest handshake refreshes during active traffic
- transfer counters increase
- session source is the dedicated Home peer

## Quick troubleshooting

### Home SSH times out

Check:

1. Home tunnel is active
2. Home peer identity matches the OPNsense peer
3. endpoint points to the local OPNsense LAN address
4. OPNsense peer contains the matching Home public key
5. Allowed IPs match the intended Home peer and AI subnet

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
