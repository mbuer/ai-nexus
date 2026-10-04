# Decision Log

## 2026-09-29 — Birdynator analysis v2 within existing boundaries

Derive selective, deterministic evidence from the existing read-only activity
and species views, then ask Birdynator for a concise narrative. Observations,
exploratory correlations, hypotheses and experimental predictions remain separate.
Use a shared historical cutoff and matching clock-hour daily comparisons to avoid
future observations and partial-day rank bias. Generated analysis remains in
`analysis_runs`; questions are not automatically promoted to canonical memory.

No infrastructure, privileges, network paths or Internet allowlists change.
External enrichment remains disabled. The deferred live ML interface remains
deferred; optional offline archive replay exercises prediction-surprise derivation
without adding access to upstream model-specific tables. See
`docs/birdynator-analysis.md` for the evidence contract and its limitations.

## 2026-09-23 — Platform scope

AI Nexus is a long-term secure agent execution platform rather than a general-purpose AI VM.

Primary qualities:

- secure
- scalable
- reproducible
- observable
- least privilege

## 2026-09-23 — Initial VM sizing

Selected baseline:

- 2 vCPU
- 8 GB RAM
- 32 GB disk

## 2026-09-23 — Virtual hardware

Selected:

- q35 machine type
- OVMF / UEFI
- VirtIO networking
- VirtIO SCSI
- Proxmox firewall enabled on VM NICs

## 2026-09-23 — Repository

Repository: `mbuer/ai-nexus`

The repository is the source of truth for architecture, decisions, configuration, and future automation.

Secrets and live environment-specific addressing must not be committed.

## 2026-09-23 — Network isolation

A dedicated Proxmox bridge (`vmbr1`) and dedicated OPNsense AI interface were selected instead of attaching AI Nexus directly to the home LAN.

The home network remains independent of OPNsense. The AI segment intentionally depends on it.

## 2026-09-23 — Single network path

AI Nexus uses only:

```text
AI_HOST -> AI_GATEWAY -> OPNsense
```

The temporary direct-LAN NIC was removed.

## 2026-09-23 — Controlled Internet access

AI Nexus uses OPNsense for:

- DNS
- HTTP/HTTPS egress
- outbound NAT
- firewall logging

Generic outbound TCP/22 is not intentionally permitted.

## 2026-09-23 — DNS through OPNsense

AI Nexus uses OPNsense as its DNS resolver.

`resolvconf` is installed and the DNS resolver is part of the persistent Debian interface configuration.

## 2026-09-23 — GitHub SSH over 443

The Git remote remains SSH-based, but GitHub SSH is redirected to `ssh.github.com:443`.

This avoids opening generic outbound TCP/22 solely for repository access.

## 2026-09-23 — Reject client-side static routing as normal management

A Windows persistent route to the AI subnet through OPNsense was tested and later removed.

The path was operationally complex and unstable.

## 2026-09-24 — Separate WireGuard peers for Home and Away

The original Home profile reused the Away peer identity.

That produced intermittent failures:

- SSH reset after initially working
- subsequent SSH attempts timed out
- restarting the tunnel temporarily restored access

The final design uses distinct peers and separate keypairs.

### Home

```text
Endpoint = local OPNsense LAN address
AllowedIPs = AI_NET
PersistentKeepalive = 25
```

### Away / work

```text
Endpoint = public WireGuard endpoint
AllowedIPs = HOME_LAN, AI_NET
```

The Home session was verified as originating from the dedicated Home peer. Separate peer identities remain the correct architecture, but later testing showed that intermittent SSH resets can still occur, so peer reuse was not the sole cause.

## 2026-09-24 — Sanitize public network documentation

The repository remains public, but exact live network addressing is no longer part of public documentation.

Rationale:

- RFC1918 addresses are not Internet-routable, but publishing exact topology and management addressing provides unnecessary environmental detail.
- The learning value is preserved by documenting roles and relationships symbolically.
- Real values belong in a local ignored configuration file.

Pattern:

```text
config/network.example.yaml   # safe example
config/network.local.yaml     # real values, ignored
```

## 2026-09-23 — Troubleshooting changes are not architecture

The following are not part of the intended final architecture:

- explicit LAN laptop -> AI Nexus SSH rule
- temporary AI -> OPNsense ICMP rule
- per-rule `Disable reply-to`
- global `Disable force gateway`
- Windows persistent route

## 2026-09-23 — IPv6

IPv6 is not enabled on the AI segment.

## 2026-09-23 — Snapshot after network cleanup

A recovery snapshot was taken after the isolated networking and management path were established.

Snapshots are recovery checkpoints, not a substitute for configuration management.


## 2026-09-24 — Debian security baseline

The Debian host now provides defense in depth in addition to OPNsense.

SSH:

- direct root SSH disabled with `PermitRootLogin no`
- public-key authentication enabled
- password authentication intentionally retained for the non-root admin account

Host firewall:

- nftables enabled persistently
- inbound and forwarding default to drop
- loopback and established/related traffic allowed
- SSH accepted only from the WireGuard management network
- ICMP and ICMPv6 retained for diagnostics
- outbound traffic accepted locally; OPNsense remains the primary egress policy boundary

Updates and logging:

- unattended upgrades enabled for the current Debian release and Debian security origins
- package lists and unattended upgrades run daily
- automatic reboot remains disabled
- systemd journal storage is persistent
- auditd and audispd plugins enabled
- targeted audit watches cover SSH configuration, sudoers, nftables configuration, local identity files, and systemd unit configuration
- an audit test confirmed configuration changes are recorded with user attribution

## 2026-09-24 — Security baseline snapshot

Snapshot:

```text
baseline-security-audit
```

Description:

```text
Hardened Debian baseline with root SSH disabled, nftables host firewall, unattended upgrades, persistent journald, and targeted auditd rules verified.
```


## 2026-09-24 — Rootless Podman runtime

Podman was selected as the initial container runtime.

Rationale:

- supports rootless containers cleanly
- avoids making a privileged Docker daemon a general agent capability
- integrates with systemd/journald
- supports per-container networking and secrets
- fits the least-privilege design of AI Nexus

The verified runtime uses `crun`, `netavark`, journald logging, and seccomp.

## 2026-09-24 — Internal container service network

A dedicated internal Podman network is used for agent-to-service communication.

Design goals:

- supporting services are not published to the host or LAN by default
- agents can reach only the services attached to the same internal network
- live container subnet details remain environment-specific and are not stored in the public repository

## 2026-09-24 — PostgreSQL as the initial agent memory backend

PostgreSQL 17 was selected as the first persistent memory backend.

Initial design:

- PostgreSQL runs as a rootless container
- no host port is published
- persistent data uses a Podman volume
- the PostgreSQL superuser credential is stored locally and injected through a Podman secret
- each agent receives a separate database identity rather than using the PostgreSQL superuser
- the first agent has its own role and database
- the first agent role has no elevated PostgreSQL attributes

The initial memory schema is intentionally structured and simple. Vector search will be added later rather than introducing a separate vector database at this stage.

## 2026-09-24 — First agent memory validation

The first agent database path was validated end to end:

```text
agent credential
    -> internal Podman network
    -> PostgreSQL
    -> agent-owned memory table
```

A temporary container authenticated using the agent credential, inserted a structured memory record, and successfully read it back.

This proves the first per-agent persistence boundary before deploying a real agent process.


## 2026-09-24 — First agent identity: Birdynator

The generic first-agent identity was renamed to **Birdynator**.

Purpose:

> A long-term personal bird analyst that builds continuity across observations, environmental data, analysis, and time.

Technical naming:

```text
display name: Birdynator
slug:         birdynator
container:    agent-birdynator
database:     birdynator
DB role:      birdynator
DB secret:    birdynator-db-password
```

The PostgreSQL role, database, and local/Podman credential naming were updated to match. Birdynator retains ownership of the existing memory table and has no elevated PostgreSQL privileges.

## 2026-09-24 — pgvector semantic-memory foundation

The PostgreSQL service image was changed from the standard PostgreSQL 17 image to the pgvector PostgreSQL 17 image while reusing the existing persistent Podman volume.

Validation confirmed that the existing Birdynator memory record survived the image change.

The `vector` extension is enabled in the Birdynator database:

```text
pgvector 0.8.6
```

The memory table now includes:

- `embedding vector(384)`
- HNSW index using `vector_cosine_ops`

The 384-dimensional shape is intended for a small local sentence-transformer embedding model. The embedding service itself is the next step.

## 2026-09-24 — Agent memory snapshot

Snapshot:

```text
baseline-agent-memory
```

This snapshot marks the first complete agent persistence milestone: rootless Podman runtime, isolated service network, PostgreSQL-backed per-agent memory, and verified Birdynator database identity.


## 2026-09-24 — Verified logical database recovery

The PostgreSQL backup workflow was tested by restoring the latest Birdynator dump into a temporary database.

Validation confirmed:

- the existing memory record was recovered
- the model-aware `memory_embeddings` table was present
- pgvector objects restored successfully under the PostgreSQL administrative recovery role
- the temporary recovery database was removed after validation

Decision: snapshots remain useful recovery checkpoints, but Birdynator also requires logical PostgreSQL backups with tested restore procedures.

The long-term backup target should live outside the AI Nexus VM and outside the agent runtime's normal write boundary.


## 2026-09-24 — Controlled OpenAI egress

Birdynator does not receive direct general Internet access.

OpenAI API traffic uses a dedicated CONNECT proxy that:

- allows only the approved OpenAI API destination on TCP/443
- preserves end-to-end TLS
- is isolated from the agent-memory database network
- publishes no host port

This preserves useful cloud reasoning without turning Internet access into an implicit agent capability.

## 2026-09-24 — BirdNET remains authoritative source data

The BirdNET monitoring PostgreSQL database remains the source of truth for detections, hourly activity, species activity, and weather.

Decision:

- do not copy raw BirdNET rows into Birdynator memory
- use a dedicated read-only PostgreSQL role
- force read-only database sessions
- provide access through a fixed-destination datasource proxy
- keep the datasource proxy separate from the agent-memory database network

This gives Birdynator useful source access without granting broad LAN access.

## 2026-09-24 — Recent activity is compared with historical context

The default Birdynator analysis compares the latest 24 hours with the preceding 30-day baseline.

The baseline excludes the recent window.

Historical context includes mean, standard deviation, p10, median, p90, min/max, and sample count where the hourly source fields are numeric. Recent species-by-hour and confidence context are also supplied.

These statistics are descriptive context. The reasoning model is instructed not to equate acoustic detections with bird abundance or infer causation from correlation.

## 2026-09-24 — Persist analyses separately from canonical memory

Successful BirdNET analyses are stored in `analysis_runs` rather than being inserted automatically into canonical memory.

Each run records:

- model
- analysis parameters
- source window/reference
- SHA-256 digest of the exact reasoning context
- generated analysis text
- timestamp

This preserves longitudinal analysis history and provenance while keeping observations, interpretations, and durable memory conceptually separate.

## 2026-09-24 — Fast Birdynator development path

Normal Birdynator code iteration uses:

```bash
make birdynator-update
```

The workflow applies pending migrations, reuses the cached Python base image by default, rebuilds only Birdynator, restarts it, and verifies its constrained service paths.

A base-image refresh is explicit through `BIRDYNATOR_REFRESH_BASE=1`.

The Birdynator image build also compiles the Python source so syntax failures are caught during the build.


## 2026-09-26 — Defer ML-to-Birdynator interface until ML evidence stabilizes

The BirdNET/Infra ML stack is still under active development.

Decision:

- continue developing and validating the ML layer before designing the Birdynator integration contract
- do not build a dedicated transport layer now; the existing datasource path is sufficient
- once the useful ML outputs are better established, expose them through a narrow read-only evidence boundary
- keep Birdynator dependent on stable analytical evidence rather than on model-specific internals, implementation details, or temporary experiment outputs

This preserves independent ML iteration now while keeping a clean future integration point for Birdynator.

## 2026-09-26 — Preserve upstream BirdNET data-quality provenance

The BirdNET/Infra project now has durable hourly station-health evidence derived from BirdNET analysis telemetry and persisted in the authoritative analytical PostgreSQL environment. The collector, historical backfill, and scheduled timer have been runtime-verified.

Decision:

- keep the health collector and health-history ownership in the BirdNET/Infra project
- do not duplicate station-health collection inside AI Nexus
- keep the existing Birdynator datasource path read-only
- when the deferred ML-to-Birdynator evidence boundary is designed, include stable data-quality provenance such as healthy, incomplete, or unknown observation coverage where it materially affects interpretation
- do not let Birdynator infer that a zero-detection hour proves biological absence when upstream station evidence is incomplete or unknown
- make no AI Nexus runtime change now; the ML-to-Birdynator interface remains deferred until the useful analytical/ML evidence contract stabilizes

This preserves the separation between authoritative environmental evidence and agent-generated interpretation.

## 2026-09-27 — Make full runtime verification explicit

`make verify` runs the existing foundation, embedding, OpenAI proxy, BirdNET proxy, and Birdynator checks in dependency order and stops at the first failure. It requires the fully deployed runtime and working external capability paths.

`scripts/verify.sh` remains the foundation-only check used by bootstrap. Bootstrap does not deploy all services, so its completion message must not imply that full runtime verification is available on a foundation-only host. No service deployment or security policy changes are part of this cleanup.


## 2026-09-30 — Record verified v2 deployment and unresolved management reliability

Operator-provided logs confirm evidence v2.1 and narrative prompt v2.2 deployed,
18 regression tests and repository hygiene passed, and full runtime verification
passed. Historical analysis completed through the controlled OpenAI path and was
persisted separately from canonical memory. Public commit `798cad6` was pushed
successfully. Generated tie wording remains a known interpretation limitation;
see [Birdynator analysis](birdynator-analysis.md).

Management SSH resets remain unresolved. Preserve the existing isolation and
separate Home/Away peers; resume targeted evidence collection when the failure
recurs. Passing application/security checks is not a management reliability fix.
[SSH troubleshooting](ssh-troubleshooting.md) is the current investigation record;
the September 23/24 document remains historical evidence. Raw logs/captures and
private Git attribution must not be copied into public documentation. See
[Repository workflow](repository-workflow.md) for publication checks.

## 2026-09-30 — Correct Home WireGuard return path narrowly

Loaded firewall rules confirmed automatic reply-to via HOME_ROUTER for local
WireGuard traffic. Apply a LAN-network to LAN-address IPv4 UDP/51820 quick pass
rule before the broad LAN allow with Disable reply-to enabled. Preserve DHCP,
the default gateway, other return-path controls and all AI isolation boundaries.
A post-change capture verified direct client replies and two handshake responses
over approximately five minutes; sustained reliability is not yet established.
This supersedes the earlier wait-for-recurrence guidance for this specific
mechanism. See [SSH troubleshooting](ssh-troubleshooting.md) for the evidence,
state-renewal procedure and bounded rollback.

## 2026-09-30 — Trial optional provider-hosted species context

The operator authorized selectively comparing BirdNET findings with trusted online
species references. Supersede the earlier no-enrichment scope only for an explicit
`--web-enrichment` trial. Use the existing OpenAI Responses connection with hosted
web search restricted to Cornell All About Birds, eBird and English Wikipedia,
with a two-tool-call cap and optional model selection of useful research. Keep
external context and source provenance separate from deterministic SQL evidence.
No agent network, firewall, datasource or proxy destination expansion is required.
The API provider enforces search-domain filtering; query minimization remains a
prompt instruction, and live model support and report quality remain to be tested.
Default reports stay local-evidence only. See [Birdynator analysis](birdynator-analysis.md).


The initial trial returned no search calls with automatic tool choice. On operator
approval, enrichment policy v2 requires a source check when explicitly enabled,
while retaining optional inclusion, the two-call cap and the same source domains.
Default runs do not research. The corrected operator handoff confirms saved run 9 included a Cornell citation with required search. This is bounded evidence of enrichment use, not a later full-runtime verification transcript.


## 2026-10-03 — Journal v1 as standalone exports (local implementation)

Refine narrative prompt v2.5 toward magazine-style stories with selective numbers
and no word target. Adapt narrative into a deterministic structured report; render
escaped HTML, Markdown and a static index without a hosted service or framework.
Persist new report objects and aggregate evidence inside the existing
analysis_runs parameters JSON, with source-digest checks before rendering metrics
or charts. Legacy saved analyses keep their original text and provenance and do
not gain invented historical evidence. Questions stay separate from canonical
memory. No Grafana, database schema, network, ML interface or isolation change.
Deployment and live prompt validation remain pending.

## 2026-10-03 — Manual Journal publication and deployment follow-up

Supersede the preparation-only status of the earlier Journal entry: operator
results confirm permanent v2.7 and v2.8 updates, each with 40 offline tests,
repository hygiene and Birdynator-specific runtime verification. These are not
claims of a later full-stack verification or proof of prose accuracy. Narrative
v2.9 was a temporary trial used for saved analysis 13, with a conditional longer
story target; permanent v2.9 installation is not established.

Use the existing Windows PC as a manually triggered artifact carrier. Read a saved
analysis through existing WireGuard SSH, render locally, then publish completed
static output over a separate LAN SSH connection to Utility. Utility does not join
the AI bridge. No transport VM, new agent network capability or automatic promotion
to canonical memory is introduced. Preserve existing authentication and keep real
configuration and private records out of public Git.

The operator published the green logo, descriptive source links and weekday dates.
Those publisher/UI changes remain in a separate workstation package pending reviewed
source integration. Deployment is not Git publication. Keep the existing repository
for now; a future split requires a concrete independent lifecycle and a report
compatibility contract. See [Birdynator Journal](birdynator-journal.md) for the
end-to-end explanation and reconstruction limitations.

## 2026-10-03 — Reconcile Journal source ownership

Prepare the repository update using permanent narrative v2.8, the reviewed Journal
renderer and final green logo. Keep the v2.9 prompt trial separate. The Windows
client invokes the one shared renderer; publication and the nginx template live
under the separate hosting component. Private records are ignored and the client
has no hard-coded live destination. Extend tracked content hygiene to Python and
PowerShell. Preserve the earlier deployment records; source integration does not
establish live deployment or remote publication. No datasource, memory, network
or credential privilege change is introduced.

## 2026-10-03 — Daily generation with manually triggered sync

Prepare one automated daily attempt at 21:00 America/Los_Angeles on AI Nexus,
starting no earlier than tomorrow when installed. Retain the existing model,
24-hour window, 30-day baseline and opt-in enrichment capability for the scheduled
command. The worker skips if a report exists that Pacific date, locks its own
instances and does not automatically retry ambiguous failures. Saved analyses
remain separate from canonical memory. No scheduled run has been verified yet.

Windows -SyncNew reads Utility's archive IDs and imports only missing saved BirdNET
analyses. Initial sync may import older trials; no model request is made by sync.
Keep publication manual and preserve existing authentication, proxies, firewall,
WireGuard and recovery boundaries. See [Daily Journal](daily-journal.md).
