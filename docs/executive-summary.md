# How AI Nexus fits together

Birdynator reads a backyard's recorded history and turns it into something worth
reading in the evening. AI Nexus supplies the bounded execution environment. The
Journal is the reader-facing result, hosted separately on Utility.

## Observations become comparisons, then interpretation

BirdNET remains the authoritative datasource. A read-only database role and a
fixed-destination proxy let Birdynator read approved views without general LAN
access. Deterministic calculations compare matching hours and each species' own
history. The model then interprets those comparisons; optional trusted-source
research supplies natural-history context, not new local observations.

A saved analysis retains its model, prompt, evidence and provenance. This makes
historical replay possible and lets a reader question an interpretation without
losing the original report. Unknown recorder coverage and uncertain classifier
identifications still limit what can be concluded.

Read [analysis](birdynator-analysis.md) for the evidence and
[the trial](journal-trial.md) for comparison before promotion.

## A capability is a narrow permission

Rootless Podman runs Birdynator without a public host port. Its own PostgreSQL
and embedding service use internal networks. OpenAI requests pass through an
allowlisted CONNECT proxy; BirdNET queries use a separate datasource proxy.
OPNsense controls routed AI traffic, WireGuard carries management, and host
nftables adds defense in depth. Each path can be tested without granting all the
others. The AI segment intentionally has no IPv6 path.

[Architecture](architecture.md), [network](network.md) and
[agent runtime](agent-runtime.md) explain those boundaries and their configuration.

## The reader does not need access to the agent

Windows reads saved reports through the existing WireGuard SSH path, renders them
locally and uploads a completed release to Utility over a separate LAN SSH path.
Publication makes no new model request. nginx serves the Journal; Utility gains
no connection to AI Nexus. Previous releases allow content rollback.

HTTPS protects a personal review login on Windows and Android. Reviews are saved
centrally on Utility, so different browsers see the same history. The proposed
Windows return transport and AI editorial store remain unfinished. Collection is
working; automated improvement is not installed.

Read [the Journal's journey](birdynator-journal.md),
[feedback](journal-feedback.md) and [HTTPS maintenance](journal-https-plan.md).

## Different records deserve different trust

Source observations stay in BirdNET. Generated reports and hypotheses live in
`analysis_runs`. Editorial reviews express preferences in a separate store.
Canonical `memory` contains explicitly accepted durable knowledge with provenance.
Neither a model summary nor a reader rating is automatically promoted into it.

The baseline is narrative v3.0 with GPT-6.1 Sol. The approved October 13–19
species-history trial emphasizes developing patterns and recent-story awareness;
previous topics guide editorial continuity, not biological evidence. The baseline
resumes October 20 unless a later reviewed decision changes it.

See [release status](birdynator-releases.md) for features and source identity.

## Recovery is part of the design

A fresh PostgreSQL logical dump must succeed before the Proxmox VM backup proceeds.
Logical restores have been tested; VM and database backups serve different recovery
needs. Utility release retention helps with publication mistakes, while its private
review queue still needs an established off-VM backup cadence and restore check.

[Backup and recovery](backup-recovery.md) explains the chain. The
[decision log](decisions.md) explains how it developed. For practical work, use
[repository workflow](repository-workflow.md); for rebuilding, use
[reproducible runtime](reproducible-runtime.md).
