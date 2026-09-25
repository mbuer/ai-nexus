# Executive Summary

## What AI Nexus is

AI Nexus is a security-focused home-lab platform for running AI agents without giving them broad trust in the host, home LAN, Internet, or supporting databases.

The project is designed around four ideas:

1. **Containment** — agents run rootless, without host-published ports, behind explicit network boundaries.
2. **Least privilege** — each capability is granted narrowly: memory DB, embedding service, OpenAI API, and BirdNET source access are separate paths.
3. **Reproducibility** — runtime definitions, migrations, build scripts, and decisions live in Git.
4. **Recoverability and provenance** — persistent state is backed up, restores are tested, and generated analysis keeps enough source metadata to be reviewed later.

## What we built

### Secure host and network boundary

AI Nexus runs as a dedicated Debian VM behind OPNsense. Management is through WireGuard. The Debian host also has a default-drop inbound/forward nftables policy as defense in depth.

Read:

- [Architecture](architecture.md)
- [Network](network.md)
- [Security baseline](security-baseline.md)

### Rootless agent runtime

Rootless Podman and Quadlet/systemd run Birdynator and its supporting services. PostgreSQL is internal-only, secrets are mounted through Podman secrets, and runtime containers use resource limits and read-only filesystems where practical.

Read:

- [Agent runtime](agent-runtime.md)
- [Reproducible runtime](reproducible-runtime.md)

### Long-term agent memory

Birdynator has a dedicated PostgreSQL login role while schema ownership belongs to a separate NOLOGIN role.

Canonical memory is kept independent from the embedding model. Embeddings are versioned separately, which makes future model changes possible without redefining the authoritative memory record.

Read:

- [Agent runtime](agent-runtime.md)
- [Embedding service](embedding-service.md)

### Controlled OpenAI reasoning

Birdynator does not receive normal Internet access. OpenAI requests go through a dedicated CONNECT proxy that allows only the approved OpenAI API destination while preserving end-to-end TLS.

The API request uses `store: false`.

### Read-only BirdNET datasource

BirdNET remains an authoritative external datasource rather than being copied into agent memory.

Birdynator connects using:

```text
Birdynator
  -> private datasource link
  -> fixed-destination BirdNET proxy
  -> BirdNET PostgreSQL
```

The PostgreSQL role is read-only, and the narrow proxy avoids granting the agent general LAN access merely to query its datasource.

Read:

- [Birdynator analysis](birdynator-analysis.md)
- [Architecture](architecture.md)

### Historical bird analysis

The default analysis compares:

- latest 24 hours
- preceding 30-day baseline

The reasoning context includes:

- hourly activity/weather
- historical mean
- historical standard deviation
- p10 / median / p90
- minimum / maximum
- sample count
- recent species-by-hour activity
- recent average/max confidence
- historical species presence/detection/confidence context

This lets Birdynator ask a more useful question than “what happened today?”:

> What changed relative to what is normally observed at this site and time of day?

Read:

- [Birdynator analysis](birdynator-analysis.md)

### Analysis history and provenance

Successful analyses are saved locally in the Birdynator database in `analysis_runs`.

Each run records:

- model used
- source window
- analysis parameters
- source reference
- SHA-256 digest of the exact reasoning context
- generated analysis
- timestamp

The raw BirdNET dataset is not duplicated.

### Backup and recovery

PostgreSQL logical backup and restore have been tested. VM snapshots/backups and logical database backups are treated as complementary recovery mechanisms.

Read:

- [Backup and recovery](backup-recovery.md)
- [Proxmox backup hook](proxmox-backup-hook.md)

## Day-to-day commands

Update Birdynator after pulling normal code changes:

```bash
git pull
make birdynator-update
```

Run the normal 24h-versus-30d analysis:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analyze-birdnet
```

List previous analyses:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analysis-history
```

Run the full runtime verification:

```bash
make verify
```

Test database recovery:

```bash
make restore-test
```

## Why the architecture matters

The agent is useful because it can combine history, source data, and model reasoning.

The platform is safer because those capabilities are deliberately **not** delivered as one broad permission.

Birdynator can:

- read its approved BirdNET datasource
- read/write its own durable state
- call the approved OpenAI endpoint
- use the local embedding service

but each path is independently constrained and observable.

That separation is the core of AI Nexus.

## Recommended reading order

1. [README](../README.md)
2. [Architecture](architecture.md)
3. [Birdynator analysis](birdynator-analysis.md)
4. [Agent runtime](agent-runtime.md)
5. [Decision log](decisions.md)
6. [Backup and recovery](backup-recovery.md)
7. [Network](network.md)
8. [Security baseline](security-baseline.md)
