# Backup and Recovery

## Goal

Birdynator is intended to retain useful state over many years. Recovery therefore needs more than VM snapshots.

AI Nexus uses two complementary layers:

1. VM-level recovery checkpoints and Proxmox backups
2. logical PostgreSQL backups with tested restore procedures

## Current state

The logical PostgreSQL backup and restore path has been verified end to end.

A restore test successfully recovered:

- Birdynator's existing memory record
- the model-aware memory embedding schema
- pgvector-backed objects

Newer logical backups also include Birdynator's persisted analysis history (`analysis_runs`) because it lives in the same PostgreSQL database.

## Security model

The final backup target should be outside the AI Nexus VM.

Preferred design:

```text
AI Nexus VM
   |
   | narrow backup transfer
   v
Off-host backup target
   |
   +-- retention/history
   +-- restore source
```

The backup target should not be exposed as a broad writable filesystem to future agent containers.

This limits the ability of a compromised or malfunctioning agent to destroy both live data and recovery history.

## Local staging

The default logical-backup directory inside AI Nexus is a staging location.

It is useful for:

- creating and validating dumps
- quick local recovery
- handoff to an off-host backup process

It is not sufficient by itself for host/disk failure.

## Restore testing

Use:

```bash
make restore-test
```

A backup policy is only considered healthy when restore testing continues to pass.
