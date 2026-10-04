# Birdynator Journal v1

Journal v1 creates mobile-first HTML with inline CSS, Markdown, structured JSON
and a static archive index. The generator is offline. A separate manual Windows
publishing workflow delivers completed files to a LAN-only nginx service on Utility.
The browser loads the logo from that same server; the Journal has no browser scripts
or third-party assets. Opening a cited source is a reader's separate navigation.
Grafana and the existing AI isolation boundaries remain unchanged.

## Current status and source ownership

October 3 operator results confirm permanent narrative v2.8 installation, saved
Journal reports and a successful Utility publication. The v2.9 longer-story prompt
was a temporary trial used for analysis 13. See the dated
[status record](../README.md#journal-status--october-3-2026) for verification scope.

The authoritative adapter, renderer and final logo are in `services/birdynator/`.
The Windows client is in [clients/windows/journal](../clients/windows/journal/README.md);
the publication helper and symbolic nginx template are in
[deploy/journal-host](../deploy/journal-host/README.md). The client invokes the shared
renderer directly, so the website and runtime do not maintain separate renderer copies.
Live addressing stays in private configuration. The hosting template still requires
comparison with the actual host before installation; it does not claim a fresh live audit.

## From observation to evening page

### Reading an observation without owning its source

BirdNET remains the authoritative source of detections. Birdynator reads approved
aggregates through the fixed-destination database proxy using a read-only role.
The proxy grants access to one datasource rather than general access to the LAN.
The source continues to own recordings and observations; the agent owns its
interpretation of them. See [Architecture](architecture.md) and
[Birdynator analysis](birdynator-analysis.md) for the service path and evidence calculations.

Deterministic evidence compares the latest window with its baseline and uses
matching clock hours for calendar-day comparisons. That scope matters: a partial
morning cannot fairly compete with a complete day's total. A new name in the
supplied history is also a classifier record, not proof of biological rarity or
a confirmed identification. Evidence provides a bounded story the model can tell.

### Turning evidence into a story that can be revisited

The model receives computed evidence through the controlled OpenAI connection.
It develops a main story, a few worthwhile discoveries and a question to watch.
Optional research uses provider-hosted search through that same API path; the
container gains no direct website access. Cited natural history supplies context,
not proof that this recorder captured a particular call or that weather caused
a change. The [analysis documentation](birdynator-analysis.md) explains source
restrictions, fallback behavior and the limits of prompt-enforced query minimization.

Successful output is saved in `analysis_runs`, with the model, source window,
parameters, aggregate evidence and provenance. It is kept separate from canonical
memory so a tentative interpretation does not quietly become an accepted fact.
The source digest identifies the exact evidence context. It does not hash the
prompt or generated story and cannot certify every sentence. Prompt versions and
run IDs therefore matter even when two stories use identical evidence.

### Carrying a completed report across the boundary

The operator manually starts `Publish-Journal.ps1` on Windows with a saved analysis
ID. The PC reads that record over the existing SSH connection through WireGuard,
using a read-only transaction. This step does not request another model analysis.
The local renderer escapes HTML and checks matching evidence before displaying
metrics or charts. Legacy records retain their prose without invented evidence.
Raw records stay in a private workstation directory; rendered report JSON and
provenance are available to Journal readers on the LAN.

The PC then uses a separate LAN SSH connection to upload completed files to Utility.
It carries an artifact between two existing administrative paths rather than
making Utility a member of the AI network. Utility needs neither an AI bridge NIC
nor a WireGuard peer for this workflow. Existing SSH authentication and host-key
checks apply; the publisher does not save passwords or private keys. This is a
manually operated administrator workflow, not a restricted unattended service.

```text
BirdNET -> scoped proxy -> Birdynator -> saved analysis
                                          |
                                 existing WireGuard SSH
                                          |
                                     Windows PC
                                  render and validate
                                          |
                                    separate LAN SSH
                                          |
                                  Utility static Journal
                                          |
                                      LAN reader
```

### Publishing a page without giving the web host an agent

Utility validates the manifest, expected filenames, file sizes and checksums before
building a completed release. Previous reports are retained and the archive is
rebuilt. Normal publication replaces the current-release symlink atomically.
The first conversion from a placeholder directory has a short switch between
retaining that directory and installing the link. nginx serves static output;
it does not execute the model or receive database credentials.

The web listener is limited to the intended LAN address and readers. Utility's
host firewall matters because ordinary same-LAN traffic does not pass through
OPNsense. The Journal's content policy allows its same-origin logo, and limits
scripts, framing and other content capabilities. Live addresses, login names and
firewall interface values belong in ignored local configuration, not public docs.

### Knowing what survives a failed attempt

A rejected upload leaves the current site in place. Completed older releases are
retained; publication also retains upload staging rather than automatically deleting
it. Retention cleanup remains an operator task. A failed render or publication
does not delete the saved AI Nexus analysis, so the same run can be published again
without paying for another model request.

For site rollback, inspect the retained completed releases and point the current
link back to the selected release using an atomic replacement. A nginx policy
change has its own retained configuration backup and must pass `nginx -t` before
reload; restoring content and restoring configuration are separate operations.
See the [hosting instructions](../deploy/journal-host/README.md) for setup and bounded rollback; inspect the actual host before making changes.
Retained releases on Utility help with publication mistakes but do not replace an
off-host backup. AI Nexus analysis history is covered by the existing PostgreSQL
and VM recovery chain described in [Backup and recovery](backup-recovery.md).

## Report contract

`services/birdynator/journal.py` defines and validates schema
`birdynator-journal-v1`. Fields are `date`, `headline`, `summary_metrics`,
`todays_story`, `findings`, `watching`, `model_surprise`, `bird_to_explore`,
`charts`, `evidence`, and `provenance`.

The model writes narrative text with known section headings, never HTML.
A deterministic adapter recognizes those headings and preserves legacy text
without guessing unsupported boundaries. Narrative is interpretation; the
watching section is a hypothesis and model-surprise prose is a prediction
interpretation. Authoritative observations, exploratory correlations, hypotheses,
experimental predictions and external source metadata remain separate in the
evidence/provenance details. The adapter does not validate every prose claim.
Legacy narrative may therefore contain more findings than the new prompt requests;
it is retained intact rather than silently truncated.

New runs store the structured report and aggregate evidence in the existing
`analysis_runs.parameters` JSON field. No raw BirdNET rows or journal hypotheses
are promoted into canonical memory. The embedded pre-insert report uses analysis
ID `pending`; export substitutes the actual row ID. Source digests cover the
evidence, not the prompt or generated prose.

Summary metrics and one optional diversity chart derive only from evidence whose
canonical SHA-256 matches `source_digest`. Metric values are checked again on
rendering. The chart is selected only when the story mentions species, diversity or variety.
It displays up to 14 comparable dates with actual date spacing, provides text values,
does not fill missing dates with zero and labels the matching-hour scope.
It is optional context rather than a claim that diversity always tells the main
story. Empty narrative sections disappear. All HTML is escaped; only bold text
and HTTPS links accepted by the existing species-source policy are rendered.
Dark mode, visible focus, semantic headings and readable contrast are built in.

## Export commands

From the existing runtime, with a writable output directory:

```bash
python /app/birdynator.py analyze-birdnet --journal-output /path/to/journal
python /app/birdynator.py export-journal 9 --output /path/to/journal
```

The second command only reads the requested analysis record. Older rows without
stored evidence export their original narrative and provenance without metrics
or a chart. It never reruns the model or silently queries historical source data.
An optional `--headline` supplies an editorial title for old reports.

Offline, without database credentials or an API call:

```bash
python services/birdynator/journal.py analysis-record.json \
  --evidence exact-evidence.json --output /path/to/journal
```

An exported record needs `id`, `source_latest_hour`, `result_text`, `model`,
`source_digest` and `parameters`. Evidence is optional but must match the digest.
Do not manufacture digests for saved runs. An editorial illustration can use an
explicit `origin` label and a digest computed from its actual replay packet;
that is not a historical model run.

Exports use date plus analysis ID so multiple runs for one day survive. Re-exporting
the same ID replaces its files. The archive rebuilds from report JSON files and
sorts by date. Dedicated export directories are recommended. Writes replace each
file atomically; the entire archive is not a concurrent multi-file transaction.
The static archive has no application search yet; browser find remains available.

## Verification boundaries

Offline tests cover HTML escaping and link policy, optional sections, evidence
digest matching, metrics, legacy reports, path validation and multiple runs.
Request/persistence boundary tests remain offline. The September 24 editorial
illustration is a labeled example, not a saved model run. Initial local-file
preview limitations are historical; subsequent browser previews and operator
publication results establish that the newer UI was reviewed and published.
They do not amount to a comprehensive accessibility or browser compatibility audit.

Operator deployment results separately record 40 tests, repository hygiene,
container build and Birdynator-specific runtime verification for the permanent
updates. Publisher checks and model prose review are distinct from those checks.
No fresh live verification was performed while updating this documentation.
