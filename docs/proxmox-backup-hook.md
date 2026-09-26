# Proxmox Backup Hook

AI Nexus VM backups use a Proxmox `vzdump` hook to create a fresh Birdynator logical PostgreSQL backup immediately before the configured AI Nexus VM is captured.

Flow:

```text
vzdump backup-start for AI Nexus VM
        |
        v
QEMU Guest Agent
        |
        v
runuser -> designated non-root admin
        |
        v
AI Nexus repository -> make backup
        |
        v
logical PostgreSQL dump staged inside AI Nexus
        |
        v
Proxmox captures VM to external backup storage
```

The hook intentionally fails the VM backup if the logical PostgreSQL backup fails.

## Install on Proxmox

The checked-in hook is a public template. Before installing it, set these values in the local Proxmox copy:

```text
AI_NEXUS_VMID
AI_NEXUS_USER
AI_NEXUS_REPO
```

Copy `proxmox/vzdump-ai-nexus-hook.pl` to an appropriate local path on the Proxmox host, make it executable, and configure that local path as the `vzdump` hook script.

Do not commit the customized production copy back to the public repository.

## Security

The Proxmox host does not mount backup storage into AI Nexus and does not open a separate SSH path into the AI segment for this workflow.

The hook uses the existing QEMU Guest Agent channel. Inside the guest it switches to the designated non-root account so the existing rootless Podman backup workflow is preserved.

The logical dump is staged inside the VM and then included in the off-VM Proxmox backup. Birdynator analysis history lives in the same PostgreSQL database, so current dumps include `analysis_runs` alongside canonical memory and embeddings.

## Verified end-to-end

The automated path has been tested successfully.

Validation confirmed:

- the `backup-start` hook fired for the configured AI Nexus VM
- QEMU Guest Agent executed the Birdynator logical backup inside AI Nexus
- the logical dump completed successfully before VM capture
- Proxmox then completed the VM backup to external storage
- the fresh PostgreSQL dump was present inside the VM at backup time

This establishes the intended recovery chain:

```text
fresh pg_dump
    ->
AI Nexus VM backup
    ->
external Proxmox backup storage
```

The logical dump remains staged inside the VM, while the durable off-VM copy is provided by the Proxmox backup archive.

For the recovery policy and restore model, see [Backup and recovery](backup-recovery.md).
