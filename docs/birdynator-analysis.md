# Birdynator Analysis

## Purpose

Birdynator is the first AI Nexus agent. It is a long-term personal bird analyst that combines authoritative BirdNET observations with local memory and controlled OpenAI reasoning.

The design deliberately separates three kinds of state:

1. **Source data** — BirdNET detections, hourly activity, species activity, and weather remain in the BirdNET PostgreSQL database.
2. **Agent memory** — durable notes, observations, hypotheses, and other canonical memory live in Birdynator's AI Nexus PostgreSQL database.
3. **Analysis history** — generated BirdNET analyses are stored separately in `analysis_runs` with provenance and model metadata.

Raw BirdNET rows are not copied into agent memory.

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

## Statistical context

Birdynator now sends the reasoning model more than simple averages.

For each hour-of-day baseline it calculates, where numeric source fields are available:

- mean
- standard deviation
- 10th percentile
- median
- 90th percentile
- minimum
- maximum
- sample count

This allows the model to distinguish a value that is merely above average from one that is outside the usual historical range.

The analysis also includes recent species-by-hour rows with:

- species
- detection count
- presence
- average confidence
- maximum confidence

Species-level comparison includes recent and historical confidence context.

These statistics remain descriptive. Birdynator is instructed not to convert correlation into causation or BirdNET detection counts into bird abundance.

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
