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
section uses local observations only by default. The optional v2.4 trial below
permits cited species context through provider-hosted search.

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


## Narrative prompt v2.3 (deployment verified)

The prompt now prefers 250-400 words for morning/partial-day reports, with shorter
reports for sparse evidence. Weather must add a distinct observation; ordinary
humidity ranks are not mandatory commentary. Follow-ups favor observable species
behavior over repeating a weather correlation. Bird-to-explore uses available
detection details and suggests listening only conditionally on recording availability.
Cautions are kept beside the relevant claim, and decorative filler is discouraged.

Tie instructions explicitly define the existing deterministic field: `ties=1` is
unique; only `ties>1` allows tied wording. Missing tie information does not support
a uniqueness claim. Evidence calculations and version v2.1 are unchanged. Prompt
version is `birdynator-narrative-v2.3`. Offline tests verify request instructions
and reproducible evidence; they do not guarantee model compliance. Operator logs subsequently confirmed all 18 tests, repository hygiene, rebuild
and full runtime verification passed. Analysis run 7 exercised the prompt. No
network or infrastructure changes were made.

The intended voice balances scientific care with an enjoyable birding story.
Personality should arise from supported species, timing and contrasts; light
phrasing is welcome, while invented motives, exaggerated rarity and forced humor
are excluded. Key numerical evidence and comparison scope remain visible.


## V2.4 optional species-context trial (operator-reported deployed)

Reports now allow slightly more statistical context: 300-450 words for partial
days and 400-550 for evidence-rich full days, without a minimum. One or two useful
statistics per finding are encouraged. Activity and diversity alone do not support
claims that no species dominates; that requires contribution evidence.

Enable enrichment explicitly:

```bash
podman exec agent-birdynator python /app/birdynator.py analyze-birdnet --web-enrichment --tier default
```

The Responses API receives the existing evidence plus the optional hosted
`web_search` tool, with `tool_choice=required`, at most two tool calls, and allowed
domains `allaboutbirds.org`, `ebird.org`, and `en.wikipedia.org` (including their
subdomains). The model must check a relevant source, but incorporates information only when
it adds value, with at
most two short, relevant connections. External species context must be cited and
kept distinct from local detections, correlations and predictions. It cannot
confirm an identification or establish a causal explanation. Local history novelty
must not be equated with biological rarity. Historical replays may use current
species references, explicitly as present-day context rather than past evidence.

Search runs on the API provider's infrastructure through the existing controlled
OpenAI connection. The container gains no direct Internet access, new proxy
allowlist entry, host port or broader network membership. This is provider-enforced
domain filtering, not a new locally enforced website proxy. Queries may be sent
to search providers. The prompt restricts them to species/general topics and forbids
private station details; this is an instruction, not a deterministic query-redaction
boundary. No station location is automatically supplied. Keep this trial opt-in.
Tool availability for the deployed model/account needs live verification; no model
substitution is performed. Search can add cost and latency.

Citation annotations are rendered into portable Markdown links. HTTPS source URLs
are checked against the domain list. Source titles/URLs, API response ID, search
call statuses, domain policy and response-received timestamp are saved under
`parameters.external_context`. This records provenance, not an exact page snapshot
or proof that the cited page entails every generated claim. The timestamp records
API receipt, not page publication or an independently observed fetch time. Evidence
hashes continue to cover SQL-derived evidence only; external results are not part
of deterministic replay and are not promoted into memory.

If the tool request is rejected with HTTP 400/422, or search returns unusable/no
citations, one new tool-free narrative request is made and the fallback is logged
and stored. Other errors, including ambiguous timeouts, are not retried
automatically. A response omitting the required search also triggers the tool-free fallback.
`--evidence-only` remains free of API calls even with the enrichment flag. Tests
cover allowlisting, citation rendering, provenance persistence, opt-in request
construction and fallback; live scientific accuracy and relevance require review.

[Official OpenAI web-search documentation](https://developers.openai.com/api/docs/guides/tools-web-search).


### Enrichment policy v2 follow-up

Trial run 8 enabled enrichment but returned no search calls or citations under
the initial automatic tool selection. Policy `species-context-v2` now requires
a source check when the flag is present, while inclusion remains optional. The
two-call cap, trusted domains, direct Internet isolation and no-web default remain
unchanged. Empty/uncited research falls back to local evidence without invented
facts; saved analysis 9 included a Cornell citation under required-search enrichment. Full runtime verification was explicitly confirmed for v2.3; no later v2.4 verification transcript is claimed.


## Journal v1 and narrative v2.5 (initial local implementation)

The corrected handoff supersedes earlier word-range preferences: the current
prompt favors a birding-magazine/data-detective voice, a strong headline, two to
four short story paragraphs, at most two additional discoveries and one question.
That initial version had no word target. Rank/tie and species-dominance errors remain known prose
quality risks; evidence derivation and prompt tests do not certify model wording.

A deterministic structured-report adapter and standalone renderer now create
HTML, Markdown, JSON and a static archive from analysis runs. New runs persist
aggregate evidence and the report in the existing parameters field. Journal v1
and prompt v2.5 were initially checked locally. This paragraph records that
preparation stage, not the current deployment. Operator results subsequently
confirmed permanent v2.7 and v2.8 updates with 40 offline tests, repository hygiene
and Birdynator-specific runtime checks. Analysis 13 used a temporary v2.9 prompt
with a conditional longer-story target; permanent v2.9 installation is not established.
See [current status](../README.md#journal-status--october-3-2026) and
[Birdynator Journal](birdynator-journal.md) for the publication workflow,
source-integration gap and validation boundaries.
