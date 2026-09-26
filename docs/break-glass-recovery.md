# Break-glass recovery

AI Nexus intentionally has no permanent bypass around OPNsense.

If OPNsense is unavailable, normal routed access to the AI segment is expected to fail. Recovery should use the Proxmox control plane rather than adding a permanent second NIC or static-route bypass.

## Preferred recovery path

Use the Proxmox web console for the AI Nexus VM.

This requires only that Proxmox management remains reachable from the normal LAN. The AI Nexus VM itself does not need working network connectivity for console access.

From the console:

1. verify the VM is healthy
2. inspect AI Nexus networking and nftables
3. inspect or repair OPNsense from its own Proxmox console as needed
4. restore normal routed access through OPNsense

## Temporary break-glass network access

If console-only access is insufficient during a prolonged OPNsense outage, a temporary host-side path may be created on the isolated AI bridge.

Conceptually:

```text
Proxmox host
    |
 temporary address on isolated AI bridge
    |
AI Nexus
```

Requirements:

- keep the AI Nexus VM attached only to the isolated AI bridge
- do not add a permanent second AI Nexus NIC to the normal LAN bridge
- do not enable permanent forwarding between the normal LAN bridge and the AI bridge
- remove the temporary Proxmox-side address immediately after OPNsense is restored
- verify the bridge returns to its normal state afterward

The exact live bridge and private addressing values are intentionally not stored in this public repository.

## What not to do

Do not use these as normal failover mechanisms:

- a permanent second AI Nexus NIC on the normal LAN
- permanent Proxmox routing between the normal LAN and AI bridge
- broad static-route bypasses around OPNsense
- disabling the AI Nexus host firewall to regain convenience

Those approaches weaken the architectural boundary and make bypass paths easy to forget.

## Recovery principle

OPNsense is allowed to be a connectivity dependency without becoming a recovery single point of failure.

Normal operation:

```text
management client -> OPNsense -> isolated AI network -> AI Nexus
```

OPNsense unavailable:

```text
management client -> Proxmox control plane -> AI Nexus console
```

The Proxmox control plane is the break-glass access mechanism.
