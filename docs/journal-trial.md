# Journal trial: offline review before a bounded live trial

## Status

Prepared locally and approved for one coherent commit/publication and a live trial
on October 13-19, 2026, at the existing 21:00 Pacific schedule. The October 12
inspection confirmed the clean baseline checkout and its installed worker/container.
This source snapshot does not record completed deployment or permanent acceptance.
Source preparation and approval alone do not activate the candidate. Baseline
narrative v3.0 remains the default and resumes October 20 after the approved window.
Do not describe original prose in a layout preview as a revised model result.

## Product goal

Explain useful changes in the recorded backyard across days, with species at the
center. Prefer developing patterns to another isolated label or empty clock-hour
slot. Preserve classifier uncertainty and coverage limits. The reader liked the
substantive October 8 replay length, but wants no filler. Candidate v3.2 removes
word quotas: each paragraph must add an observation, comparison, explanation or
relevant cited context. Quiet days may be short; optional sections may disappear.

The baseline is seven real reports, October 5-11, 2026, analysis IDs 16-22,
generated with GPT-6.1 Sol and narrative v3.0. Preserve exact originals, evidence
digests, prompt/model identifiers and source cutoffs outside public Git.
Ordinary days belong in the review; add a genuinely low-change or coverage-limited
case when available rather than manufacturing one from a model headline.

## Offline feature

`services/birdynator/trial_review.py` is independent of the live agent CLI. It
never opens a database or network connection, calls a model, saves an analysis
run or changes canonical memory. Given a saved report, it prepares an API request
for later authorized review and a static preview retaining the original prose.
The trial prompt is separately versioned as `birdynator-narrative-v3.1-trial`.

With a historical CSV snapshot, first rebuild the original evidence using its
exact cutoff/window. Stop a longitudinal replay if the digest differs. The
snapshot may contain later corrections and is not automatically the historical
state originally seen by the agent. Matching the existing digest verifies the
original derived evidence, not every raw source row or every future extension.
Record snapshot hashes and export time with the evaluation.

Compare two seven-day periods with the same local clock hours through the source
cutoff. Summarize species detected days, occupied bins, detection totals and
changes in the recorded species lists. Do not identify individual birds or call
counts abundance. Positive labels do not establish confirmed identification.
Retain the reported range of hourly maximum confidence scores and the number of
bins reporting them. This is not a range of all individual detection scores or
a calibrated identification probability; missing confidence remains unknown.

No-record bins remain `no_record_unknown_effort`; never turn missing telemetry
into biological zeroes. An aggregate-complete day is a day with all required
weather-backed activity rows, not a healthy recorder day. Both windows need seven
aggregate-complete dates before frequency-change candidates are nominated.

Initial editorial heuristics nominate repeated recent records (at least four
recent detected days versus at most one earlier day) or a difference of at least
three detected days. These are transparent, exploratory selection rules, not
significance tests, biological arrival/departure rules or validated alerts.
Do not tune them until every historical day produces an exciting story.

The editorial context retains only prior analysis/model/prompt identifiers,
cutoffs and earlier explore-selection topic keys from verified saved evidence.
It deliberately does not copy earlier narrative claims. This is a limited first
continuity signal, not a complete ledger of all topics discussed. The live candidate
uses the same limited explore-selection hints from at most fourteen earlier
archive records; it cannot claim every earlier question was tracked or answered.

Example (offline only):

```text
python services/birdynator/trial_review.py --report SAVED_REPORT.json --output REVIEW_DIRECTORY
python services/birdynator/trial_review.py --report SAVED_REPORT.json --snapshot SNAPSHOT_DIRECTORY --output REVIEW_DIRECTORY
```

CSV filenames are `bird_activity_hourly.csv` and `bird_species_hourly.csv`.
No new datasource, health-table access, reader grant, timer or SQL object is needed
for this offline prototype. A richer coverage contract is a separate proposal,
not an assumed infrastructure prerequisite or permission expansion.

## Explicit three-day API replay

The operator approved replaying October 5, 8 and 11 with GPT-6.1 Sol and the
existing trusted-source enrichment policy. `trial_replay.py` is a manually invoked
helper, not an installed agent command or daily-worker change. It uses the
existing agent secret and controlled Responses connection and performs no database
operations. Preflight checks all three requests, source digests, cutoffs, model,
prompt, chronological order and enrichment domains before the first attempt.

Make one provider request per selected report with at most two approved search
tool calls. Do not automatically fall back, retry a rejected/ambiguous request,
or proceed to the next day after an error. Preserve any completed or partial
provider output and record a needs-review state. Missing usable citations are
flagged for human review, not silently promoted into trusted facts.

The private Windows operator records the batch and attempt before SSH execution,
retains streamed events/results, and refuses to repeat an already recorded attempt.
Results keep their own trial run IDs, the original source analysis IDs, prepared
and actual request hashes, the actual API payload, source/snapshot identities,
prompt/model version, response, usage and enrichment provenance. Original reports
and live `analysis_runs` are untouched. Current web references are replay-time
context, not material proved available at the original historical cutoff.

Read original and trial versions from a separate local comparison index. The
same model identifier does not guarantee identical model weights or deterministic
output across dates; this is an editorial comparison, not a controlled scientific
validation. Live rollout and repository publication remain separate approval gates.

## Reading layout

Keep the green visual identity and a comfortable single main reading column.
Order: headline/date/source cutoff/reading time; main story; supporting species
comparison when available; a meaningful follow-up; optional discoveries or cited
species context; one useful question; collapsed coverage/provenance; review area.
Place a visual beside the passage it explains. Do not require a diversity graph.
An eventual species timeline must distinguish detections, supported zeroes and
unknown coverage. The first preview has original prose only, no invented species
chart and no newly generated follow-up. Essential uncertainty stays near its claim.

## Evaluation gates

1. Freeze the original review cohort and source snapshot; inspect mismatches.
2. Obtain authorization for the bounded model replay, including optional trusted
   enrichment and API cost. Keep the same model and source cutoffs for comparison.
3. Save trial results separately with source analysis ID, trial prompt/version,
   exact request hash, model, source evidence digest and snapshot identity. Retain
   responses and enrichment provenance; never overwrite original reports.
4. Review useful information, support, repetition, continuity and reading pleasure.
   Measure length as a supporting preference, not a target to fill.
5. Only after review, approve a seven-day live rollout with actual start/end dates,
   one trial attempt per day, explicit trial labeling, retained rollback artifacts,
   versioned selection/renderer policy, and a documented automatic return to the
   accepted baseline at the end. Do not activate it indefinitely through a flag.
6. Human review decides accept, revise or revert. Neither ratings nor elapsed days
   automatically approve production. Failed/ambiguous model calls are inspected
   before any retry; do not generate duplicate daily reports to compare versions.

The three authorized replay requests completed, with originals retained separately.
The v3.1 request builder and replay helper remain frozen for reconstruction. The
next candidate is v3.2; offline tests do not establish its future prose quality.

## The seven-day candidate and its return path

`journal_trial.py` builds the v3.2 request. Only explicit paired trial date flags
enable it. The ordinary CLI stays on narrative v3.0. The container definition adds
the two local helper modules; its networks, secrets, capabilities and model tiers
remain unchanged. The existing code-only Birdynator update rebuilds and restarts
that agent to make these files available; a full platform deployment is unnecessary.

The candidate extends observations already queried through the two approved views.
It adds the matched species history to the evidence packet before hashing it.
Earlier topic identifiers are read in a read-only transaction from `analysis_runs`
and passed separately. Their request impact is captured in the actual request
hash, never represented as source observations. No extra source grant is needed.

Trial analyses retain the normal analysis type and existing schema. Parameters
retain start/end dates, candidate policy/prompt version, actual API payload/hash,
editorial topic identifiers, response ID, usage and citation-review state. The
saved Journal carries this provenance and optional `who_is_changing` and
`following_up` interpretation sections. Both are additive v1 fields; existing
reports remain renderable. No canonical memory or feedback store is written.

Each eligible daily attempt uses the trial instead of generating a second report.
It makes exactly one provider request, with existing bounded enrichment when
enabled. A rejected request or invalid citations fail without another model call.
Missing research/citations are labeled for review, not silently treated as trusted
context. Existing daily locks, start guard, saved-today check and pre-call attempt
receipt remain active. Failed days are not filled automatically.

After the final Pacific calendar date, the same worker omits trial flags and uses
the accepted baseline automatically. Seven dates do not guarantee seven successful
reports. No automatic extension or acceptance occurs. A manual trial CLI request
outside its dates refuses before datasource/API work. The ordinary CLI remains
available; do not run it concurrently with the scheduled worker.

After approval, update the reviewed agent source using the existing Birdynator-only
procedure and run offline tests and isolation verification. Then, as the existing
non-root operator, configure a future start date:

```text
python3 scripts/configure-journal-trial.py --start YYYY-MM-DD
```

This checks the running container's candidate version without an API call, takes
the existing generation lock, verifies the installed worker hash, retains worker,
config and installation-receipt backups, and installs only the reviewed worker and
private trial policy. It preserves the schedule, timezone, start guard and other
installed-file hashes. It does not modify units, restart timers/services, request
a report or publish anything. Unknown worker edits cause refusal. Interrupted
multi-file installation requires inspection of the retained backups before retry.

To end the trial early for future generation:

```text
python3 scripts/configure-journal-trial.py --disable
```

This removes the private trial policy without deleting reports, resetting attempt
receipts, changing the schedule or cancelling a running model request. The accepted
baseline is still present in the candidate image. Image rollback is a separate
recovery action using the retained pre-update image if the code itself is faulty.

Update the Windows shared renderer from the same reviewed source before manual
sync. Trial pages and their homepage entries are labeled `Journal trial`; overview
labels contain no analysis numbers. Pages put useful species comparisons after
the lead, followed by follow-up, discoveries, cited species context and a useful
question. Provenance is collapsed; actual API payload remains in structured JSON.
There is no mandatory diversity chart, writable endpoint or feedback panel.
Utility needs only the usual static release publication, with no service/CSP change.
Latest-ID-per-source-date selection remains unchanged; trial publication is therefore
an explicit reading experiment, not a declaration of production acceptance.

After the reading period, compare substantive value, repetition, support and quiet
day behavior. Accepting the candidate permanently requires a separately reviewed
default change and explicit human confirmation. Merely reaching the end does not
promote its prompt, generated hypotheses or editorial context.

## Feedback and memory boundaries

No feedback submission is implemented in the preview. First use a manual review
record or locally saved feedback file, tied to analysis ID, model/prompt version,
evidence digest and optional section. A separate editorial store and explicit
Windows transfer/import are proposals. Never assume Utility may accept writes or
that a new public endpoint is permitted. Client scripting or CSP changes require
a reviewed design as well; local storage alone does not make a design approved.

Source observations remain in BirdNET. Generated reports/hypotheses remain in
`analysis_runs`. Feedback/preferences stay in a separate editorial record.
Canonical `memory` is explicitly accepted durable context with provenance, not
automatic model output. No prompt rewriting, retraining or memory promotion is
triggered by feedback or report summaries.

## Change discipline

AI Nexus infrastructure stays frozen; preserve WireGuard, OPNsense, proxies,
read-only datasource access and Internet isolation. Do not modify Grafana.
Do not move upstream ML/health ownership into the agent repository. The October 11
experiments support retaining the existing prediction reference; their results
are not a reason to disable production ML or assert weather is irrelevant.

Obtain operator approval before remote AI Nexus Git access, commits and pushes.
Use one coherent commit for this Journal evaluation/trial feature, including code, regression
tests and this documentation. A later feedback feature is a separate commit.
