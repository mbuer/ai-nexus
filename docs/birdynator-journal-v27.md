# Birdynator Journal and prompt v2.7

Historical v2.7 preparation record. Its pending-deployment statements describe
that stage; see [current Journal status and workflow](birdynator-journal.md)
for subsequent deployment, publication and source ownership.

Prompt v2.7 follows the magazine/data-detective brief: a short specific headline,
one main story, up to two distinct findings, one useful question, and optional
cited species context. Supporting ranks stay out of the prose unless central.
Count, confidence and identification caveats are stated once. Species behavior
from a reference cannot be turned into an imagined local scene. Sunrise-relative
language requires supplied sunrise evidence for the detection being described.

The journal adapter persists an aggregate evidence snapshot and structured report
in `analysis_runs.parameters`, leaving generated prose in `result_text`. No new
table, migration, canonical-memory write, ML interface or network capability is
introduced. The model writes Markdown; escaped HTML, JSON, Markdown and archive
pages are rendered deterministically. Metrics and a story-relevant diversity
chart require evidence matching the stored digest and cutoff. Generated claims
still require editorial review; prompt instructions are not a scientific validator.

Saved exports support both new reports and legacy prose without inventing data:

```sh
podman exec agent-birdynator python /app/birdynator.py analyze-birdnet --hours 24 --baseline-days 30 --web-enrichment
podman exec agent-birdynator python /app/birdynator.py analysis-history --limit 3
```

The existing manually triggered publisher reads the selected saved record through
the operator's existing management SSH path, renders on the Windows PC, and
uploads static files to the separate LAN journal host. No hosting credential is
installed in Birdynator. Hostnames, addresses and user identities belong in local
operator configuration, not this public repository.

The v2.6 temporary-container trial was operator-run and persisted a new analysis
with evidence and enrichment provenance; the journal was successfully published.
Its editorial review motivated v2.7: fewer incidental ranks, less repetition,
shorter headlines and a clearer boundary between external facts and local events.
v2.7 has only been validated offline. Deployment and a fresh live analysis remain
pending until the operator applies and verifies this package.

Permanent installation adds only the journal Python module to the Birdynator
image recipe. Build with the existing `make birdynator-build`, restart only the
existing Birdynator user service, then run `make birdynator-verify`. This package
does not run migrations or install a new container service definition. Preserve
the current isolation, proxies, secret mounts, firewall and WireGuard rules.
