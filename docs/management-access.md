# Management Access

## Purpose

This document describes how to reach AI Nexus safely from home and while remote.

AI Nexus does not expose a normal management path directly to the home LAN. SSH enters through WireGuard.

## Addresses

```text
Home LAN            192.168.1.0/24
OPNsense LAN        192.168.1.25
WireGuard network   10.10.10.0/24
AI network          10.50.0.0/24
AI Nexus            10.50.0.10
SSH                 TCP/22
WireGuard           UDP/51820
```

## Home profile

Use when physically connected to the home LAN.

```ini
[Peer]
AllowedIPs = 10.50.0.0/24
Endpoint = 192.168.1.25:51820
PersistentKeepalive = 25
```

The remaining client settings are copied from the existing working peer configuration.

Do not commit private keys to this repository.

### Expected routes

With the Home profile active:

```text
192.168.1.0/24 -> local Wi-Fi/Ethernet
10.50.0.0/24   -> WireGuard
```

There should be no Windows persistent route for `10.50.0.0/24`.

### Test

```powershell
ssh mb@10.50.0.10
```

The SSH login source seen by AI Nexus should be the WireGuard client address, not `192.168.1.x`.

Normal home-lab access to `192.168.1.x` devices should continue to work directly.

## Away / work profile

Use when outside the home LAN.

```ini
[Peer]
AllowedIPs = 192.168.1.0/24, 10.50.0.0/24
Endpoint = <public-wireguard-endpoint>:51820
PersistentKeepalive = 25
```

This profile provides access to:

- home-lab devices on `192.168.1.0/24`
- AI Nexus on `10.50.0.0/24`

## Why two profiles

Using the public WireGuard endpoint from inside the home network depends on NAT loopback/hairpin behavior from the Spectrum router.

Using `192.168.1.25:51820` at home avoids that dependency.

The Home profile intentionally excludes `192.168.1.0/24` from `AllowedIPs` so local lab traffic does not get pulled into the tunnel.

## Reusing credentials

The two profiles may reuse the same WireGuard client:

- private key
- tunnel address
- server public key
- peer identity

Only the routing intent and endpoint differ.

Do not activate both profiles simultaneously.

## GitHub access from AI Nexus

The Git remote uses SSH:

```text
git@github.com:mbuer/ai-nexus.git
```

The AI egress policy does not broadly allow outbound TCP/22.

AI Nexus therefore uses:

```text
~/.ssh/config
```

with:

```sshconfig
Host github.com
    HostName ssh.github.com
    Port 443
    User git
```

This keeps the existing SSH key and Git remote while using TCP/443.

Quick validation:

```bash
ssh -T git@github.com
cd ~/projects/ai-nexus
git pull
```

## Windows cleanup

The old workaround route is no longer required.

If it ever reappears:

```cmd
route delete 10.50.0.0 mask 255.255.255.0 192.168.1.25
```

Confirm:

```cmd
route print
```

Expected:

```text
Persistent Routes:
None
```

## OPNsense dependency

Management requires:

- WireGuard tunnel active on OPNsense
- firewall permission from `10.10.10.0/24` to `10.50.0.10:22`
- AI interface `10.50.0.1/24` available

No separate direct LAN -> AI SSH rule is required.

## Stability validation

For a practical management-path test, keep an SSH session active while generating outbound traffic from AI Nexus.

Suggested checks:

```bash
ping -c 120 10.50.0.1
curl -4 -L -o /dev/null https://speed.hetzner.de/100MB.bin
git fetch --all
```

During the test:

- keep the SSH session open
- run commands interactively every few minutes
- watch for freezes, resets, packet loss, or DNS failures

A stable run under sustained traffic is stronger evidence than an idle SSH session alone.

## Quick troubleshooting

### No handshake at home

Check that the Home profile endpoint is:

```text
192.168.1.25:51820
```

### Handshake works but SSH fails

Check:

1. WireGuard client address is in `10.10.10.0/24`
2. OPNsense WireGuard firewall rule allows TCP/22 to `10.50.0.10`
3. AI Nexus is listening on SSH
4. `10.50.0.10` still uses `10.50.0.1` as its gateway

### Git pull hangs

Check whether GitHub SSH is still configured for TCP/443:

```bash
ssh -G github.com | grep -E '^(hostname|port|user) '
```

Expected:

```text
hostname ssh.github.com
port 443
user git
```

### Home lab disappears when WireGuard starts

The Home profile probably includes `192.168.1.0/24` in `AllowedIPs`.

It should include only:

```text
10.50.0.0/24
```
