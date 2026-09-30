# Birdynator Analysis

## Purpose

Birdynator is the first AI Nexus agent. It is a long-term personal bird analyst that combines authoritative BirdNET observations with local memory and controlled OpenAI reasoning.

The `analyze-birdnet` command currently uses SQL-derived evidence directly; it does not retrieve canonical memory or call the embedding service. Memory-assisted questions use the separate `ask` command.

The design deliberately separates three kinds of state:

1. **Source data** — BirdNET detections, hourly activity, species activity, and weather remain in the BirdNET PostgreSQL database.
2. **Agent memory** — durable notes, observations, hypotheses, and other canonical memory live in Birdynator's AI Nexus PostgreSQL database.
3. **Analysis history** — generated BirdNET analyses are stored separately in `analysis_runs` with provenance and model metadata.

Raw BirdNET rows are not copied into agent memory.

The upstream BirdNET/Infra project also owns durable station-health/data-completeness provenance, and that path is now deployed and runtime-verified. Birdynator does not collect that telemetry itself. When the future ML/evidence interface is defined, Birdynator should consume stable upstream quality evidence where relevant so an incomplete or unknown observation hour is not interpreted as a confirmed biological absence.

## Data path

```text
BirdNET PostgreSQL
    |
    | read-only database role
    v
fixed-destination BirdNET proxy
    |
    | private Podman link
    v
Birdynator
    |
    +--> local embedding service
    |
    +--> controlled OpenAI CONNECT proxy --> api.openai.com:443
    |
    v
Birdynator PostgreSQL
  - memory
  - memory_embeddings
  - analysis_runs
```

The Birdynator container has no host-published port and no general Internet path. The BirdNET source connection is read-only, and the fixed-destination proxy prevents the agent from receiving general LAN access merely to query the datasource.

## Current analysis

Default comparison:

- recent window: **24 hours**
- baseline: **previous 30 days**
- baseline excludes the recent window
- default model tier: **Terra**

Run:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analyze-birdnet
```

Optional example:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analyze-birdnet \
  --hours 48 \
  --baseline-days 30 \
  --tier deep
```

## Analysis v2: deterministic evidence, selective narrative

`services/birdynator/evidence.py` derives a versioned `interesting_signals`
packet using only the two existing SQL views. Both reads use a shared cutoff and
a repeatable-read, read-only transaction. All positive species rows participate;
`--top-species` remains accepted for compatibility but no longer filters evidence.
No migrations, new grants, services, upstream ML integration, or network changes
are required. Infrastructure remains frozen by default.

The evidence separates:

| Field | Meaning |
| --- | --- |
| `observations.today` | Activity, distinct-species, humidity and temperature ranks, tie counts and actual sample sizes; raw detection total |
| `observations.novelty.first_seen_in_window` | Species without earlier detections in the bounded history; count, first recent hour and maximum classifier confidence |
| `observations.novelty.returning_after_gap` | Species detected again after at least seven days without a recorded detection |
| `observations.unusual_hours` | Up to three previously unrecorded species/clock-hour combinations, requiring at least five historical presence dates |
| `observations.sunrise_relative_shift` | Activity-weighted timing shift of at least one hour against the median of at least seven baseline days |
| `observations.emerging_trends` | Three consecutive comparable days all at least 1.5 times, or at most half, a prior median with at least seven days |
| `correlations` | Strongest two of eight predefined weather/activity or weather/diversity Spearman associations; at least ten baseline pairs and absolute rho >= 0.3 |
| `hypotheses` | An explicitly unconfirmed question grounded in a selected association or coincidence; no automatic memory or tracking |
| `predictions` | Separate optional experimental archive evidence; live ML integration remains deferred |
| `bird_to_explore` | First-seen species, then returnee, selected by detection count, maximum confidence and name; otherwise species with most recent occupied hours |

Ranks use **matching local clock hours from midnight through the cutoff hour**
on each date, not a partial day against full days. Rank 1 is highest and ties use
competition ranking. A 23:00 cutoff compares complete calendar days. The recent
window remains configurable and is excluded from the historical rank/correlation
baseline. Multi-day recent windows still describe the latest calendar day in
`today`; novelty spans the entire recent window.

The `ties` field counts all comparable days equal to the reported value, including the current day: `ties: 1` means unique, not tied with another day.

V2.1 adds temperature `rank_asc` (1 = coolest), `rank_desc` (1 = warmest),
`minimum_f` and `maximum_f`. The prompt requires an explicit rank for the same
metric before using a historical superlative; a correlation does not establish
an extreme day. This reduces unsupported claims but is not a deterministic
validator of generated prose.

`coverage` records the comparison scope, excluded incomplete dates and selection
rules. Missing activity hours are not zero-filled. Weather fields require all
matched hours on each included day. The weather-backed activity view does not
establish recorder uptime: health remains unknown, and detection gaps do not prove
biological absence. First seen means within supplied history, never first-ever.
These exploratory correlations do not control seasonal change or recording effort
and are not significance tests. Maximum confidence is a classifier score, not
independent species confirmation. Sunrise timing is hourly and activity-weighted,
not an estimate of an individual bird's arrival time.

The current source contract aggregates one station. Multiple station IDs or
duplicate activity/species hours fail explicitly; selecting/aggregating multiple
stations or resolving repeated local DST hours requires a future source contract.

The prompt leads with **Today's story**, followed by **What caught my eye**,
**Something to watch**, optional **Model surprise**, and **Bird to explore**.
It asks for one main finding and at most two additional findings, usually in
400-600 words on evidence-rich days, with shorter reports on quiet days and no
minimum length. Narrative prompt v2.2 develops the main finding, includes a
joint first-place humidity/diversity coincidence when at least seven comparable
days support those ranks, and distinguishes that coincidence from historical
correlation. Additional sections develop distinct findings and one testable
follow-up question. Shared identification caveats appear once; middle-ranking
temperature ordinals and repeated species statistics are discouraged.
There is no hourly inventory or repeated generic caveat. The explore
section uses local observations only: no web enrichment, external facts or links.

### Deployment verification and known output limitation

Operator-provided September 2026 logs confirm evidence v2.1 / prompt v2.2 built,
deployed and ran successfully. All 18 offline tests, `make repo-check`, Birdynator
update verification and full `make verify` passed. The source connection remained
read-only and direct agent Internet egress remained blocked. A historical model
analysis completed and was persisted in `analysis_runs`.

The live September 24 replay had 28 comparable days, while the bounded archive
replay had 25. Different source coverage explains the sample-size difference;
do not present the archive as an identical historical database snapshot.

The earlier unsupported “coolest day” claim was absent in the v2.1/v2.2 reruns
after explicit temperature ranks were added. However, the v2.2 output described
diversity and humidity as tied for first despite `ties: 1` for both. This wording
error remains open. Tests validate derivation and request construction, not every
claim in generated prose; there is no deterministic prose validator. No new
prompt correction or infrastructure change is claimed by this documentation update.

### Historical replay and inspection

Use the same SQL path without an API call or analysis write:

```bash
podman exec agent-birdynator python /app/birdynator.py analyze-birdnet \
  --through 2026-09-24T23:00:00 --evidence-only
```

`--through` is an hour-aligned, offset-free station-local timestamp. Without it,
the latest activity hour remains the cutoff. Hours must be 1-168 and baseline
days 1-366. A missing cutoff row fails explicitly.

Replay exported CSVs locally without a database, credentials, API call or writes:

```bash
python3 services/birdynator/evidence.py /path/to/export \
  --through 2026-09-24T23:00:00 > evidence.json
python3 services/birdynator/evidence.py /path/to/export \
  --through 2026-09-27T23:00:00 --with-predictions > evidence-with-ml.json
make test
```

The export directory contains `bird_activity_hourly.csv` and
`bird_species_hourly.csv`; the optional flag also reads
`bird_activity_predictions.csv`. No other archive files are needed. Python 3.12
is supported; archive ML replay needs the America/Los_Angeles timezone database
(system zoneinfo or `tzdata`). Standard-library offline tests cover evidence,
cutoffs, missing data, ties, prompt/request construction and SQL boundaries.
They cannot guarantee exact language from a nondeterministic reasoning model.

ML replay only accepts predictions created **before the target hour**, with an
explicit creation timezone, and joins actuals from observations rather than
trusting saved scoring columns. It selects the latest eligible forecast per
model/hour and at most three misses with absolute residual >=10 and >= the
predicted magnitude (minimum denominator 1). It does not certify the underlying
model's training lineage. No live model-specific tables are queried or newly
granted to Birdynator; the deferred ML evidence boundary is preserved.

For a historical replay, all observational timestamps after the cutoff are
excluded. The archive is still a later export: it cannot reproduce historical
database revisions or prove exactly which backfilled rows were available then.

## Analysis persistence

Successful analyses are stored in `analysis_runs`.

Each record includes:

- analysis type
- model used
- source type
- human-readable source reference
- latest source hour
- recent-window length
- baseline length
- SHA-256 digest of the exact source context sent for reasoning
- analysis parameters
- generated analysis text
- creation time

This preserves provenance without duplicating the raw BirdNET dataset.

V2 parameters include evidence and prompt versions and the requested cutoff.
The source digest covers the exact canonical JSON used in the request. Preserve
the export and code revision when exact evidence reproduction is needed.

It does not hash the instructions, model response or entire request. The same evidence can therefore retain its digest across prompt revisions; distinguish runs using the stored prompt/evidence versions, model and parameters as well.

List recent analyses:

```bash
podman exec agent-birdynator \
  python /app/birdynator.py analysis-history
```

The OpenAI request uses `store: false`; AI Nexus keeps the analysis record locally.

## Trust model

Treat an analysis as an interpretation, not as source truth.

Birdynator should:

- clearly separate observations from hypotheses
- use confidence and sample-size information when judging isolated detections
- identify limitations in the baseline
- avoid claiming weather caused a behavior change from correlation alone
- avoid treating repeated acoustic detections as individual bird counts
- retain enough provenance to reproduce or challenge a conclusion later

## Operational update path

For normal Birdynator code changes:

```bash
git pull
make birdynator-update
```

This applies pending database migrations, reuses the cached Python base image by default, rebuilds only Birdynator, restarts it, and runs Birdynator verification.

To deliberately refresh the Python base image:

```bash
BIRDYNATOR_REFRESH_BASE=1 make birdynator-update
```

A full `make birdynator-deploy` remains appropriate when proxy/runtime infrastructure itself changes.
