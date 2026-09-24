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

`vmbr1` is an internal Linux bridge used only for the isolated AI segment.

- No physical bridge port
- No Proxmox host IP
- OPNsense AI interface attached
- AI Nexus attached

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

ICMP from WireGuard remains blocked by default, so ping/traceroute may fail even when SSH works.

### Local laptop

The Spectrum router does not provide a route to `10.50.0.0/24`, so the Windows laptop uses:

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

When WireGuard is active remotely, its direct route to `10.50.0.0/24` has a lower effective metric and is preferred over the local static route.

## Validation

Confirmed:

- `10.50.0.10 -> 10.50.0.1` ICMP
- DNS via `10.50.0.1`
- HTTPS egress through OPNsense
- outbound NAT
- remote SSH over WireGuard
- local SSH via OPNsense
- firewall logs show expected allow/deny behavior
