# Proxmox Backup Hook

AI Nexus VM backups use a Proxmox `vzdump` hook to create a fresh Birdynator logical PostgreSQL backup immediately before VM 104 is captured.

Flow:

```text
vzdump backup-start for VM 104
        |
        v
QEMU Guest Agent
        |
        v
runuser -> mb
        |
        v
cd /home/mb/projects/ai-nexus && make backup
        |
        v
logical PostgreSQL dump staged inside AI Nexus
        |
        v
Proxmox captures VM to backup-t7
```

The hook intentionally fails the VM backup if the logical PostgreSQL backup fails.

## Install on Proxmox

Copy `proxmox/vzdump-ai-nexus-hook.pl` to:

```text
/usr/local/sbin/vzdump-ai-nexus-hook.pl
```

Make it executable and configure:

```text
script: /usr/local/sbin/vzdump-ai-nexus-hook.pl
```

in `/etc/vzdump.conf`.

The hook ignores all VM IDs except 104.

## Security

The Proxmox host does not mount the T7 into AI Nexus and does not open SSH access into the AI subnet.

The hook uses the existing QEMU Guest Agent channel. Inside the guest it switches to the non-root `mb` account so the existing rootless Podman backup workflow is preserved.

The logical dump remains a staging artifact inside the VM and is then included in the off-VM Proxmox backup stored on `backup-t7`.
