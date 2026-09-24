# Network

## Target topology

```text
Home LAN / Internet
        |
    OPNsense
        |
   AI 10.50.0.1/24
        |
      vmbr1
        |
    ai-nexus
   10.50.0.10/24
```

## Current state

### Proxmox

- `vmbr1` is an internal Linux bridge.
- It has no physical bridge port.
- It has no Proxmox host IP assigned.
- It exists only to connect OPNsense and isolated AI workloads.

### OPNsense

- AI interface: `vtnet1`
- Address: `10.50.0.1/24`
- IPv6: disabled on the AI interface
- Gateway: none
- Private/bogon blocking: disabled because this is an internal RFC1918 network

### ai-nexus

- `ens18`: temporary existing LAN interface; still present during migration
- `ens19`: isolated AI interface
- Temporary test address: `10.50.0.10/24`

The isolated interface configuration is not yet persistent.

## Firewall validation

A temporary explicit rule was added on the OPNsense AI interface:

- Action: Pass
- Direction: In
- Protocol: IPv4 ICMP
- Source: AI network
- Destination: This Firewall

After applying the rule, `ai-nexus` successfully reached `10.50.0.1`.

This confirms the Layer 2/Layer 3 path:

```text
ai-nexus ens19
    -> vmbr1
    -> OPNsense vtnet1
```

## Intended policy

The final policy should be default-deny and purpose-specific:

- WireGuard -> AI VM: allow only required management services
- AI -> home LAN: deny by default
- AI -> Internet: explicitly controlled
- AI -> DNS: explicitly controlled
- Internet -> AI: no direct inbound exposure
- IPv6: disabled until it is deliberately designed and filtered

The existing main-LAN path must remain only until routing, DNS, egress, and remote management through OPNsense have been validated.
