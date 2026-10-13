# Working efficiently in this repository

## Establish context before changing files

1. Read `README.md` for current state and ownership. Inspect Git status and HEAD
   before editing an existing checkout; do not infer deployment from Git history.
2. Read the relevant subsystem document, then its implementation and tests.
   Consult `docs/decisions.md` for cross-cutting changes or apparently conflicting
   historical guidance. Avoid rereading unrelated chapters.
3. Follow `docs/repository-workflow.md` for approvals, public hygiene and safe
   reconciliation. Private logs and live configuration are not source material.

## Find the right entry point

| Task | Start here |
| --- | --- |
| Evidence, prose, provenance | `docs/birdynator-analysis.md`, `services/birdynator/` |
| Rendering or Windows publication | `docs/birdynator-journal.md`, `clients/windows/journal/` |
| Schedule or trial | `docs/daily-journal.md`, `docs/journal-trial.md` |
| Feedback, HTTPS or Utility | `docs/journal-feedback.md`, `deploy/journal-host/README.md` |
| Network or management | `docs/architecture.md`, `docs/network.md`, `docs/ssh-troubleshooting.md` |
| Runtime or recovery | `docs/reproducible-runtime.md`, `docs/backup-recovery.md` |
| Release identity | `docs/birdynator-releases.md` |

Use `rg` and narrow reads; batch independent searches. Follow source ownership
instead of copying renderers, contracts or configuration generators. Keep shared
rules in their authoritative module and link documentation rather than duplicating it.

## Make and verify the smallest coherent change

- Preserve unrelated edits and private/recovery files. Stage explicit intended paths.
- Keep code, meaningful regression tests and operating documentation together.
- Run `make test` for Python changes and the browser test for feedback JS changes.
  Run `make repo-check` and staged whitespace checks before publication.
- Use live checks only when the change needs them and approval covers them.
  `make verify` needs deployed services; `make birdynator-update` applies migrations
  and restarts Birdynator. Docs-only changes need neither a rebuild nor a model call.
- Read retained receipts before retrying interrupted paid calls or installations.
  Do not stack changes on an unexplained failure.
- Report what changed, what passed, what remains unverified and whether source,
  publication and installed runtime now agree. Never claim a check that did not run.

Keep human docs concise: explain a mechanism and its purpose, then link to details.
Record durable design changes in the decision log and user-visible releases in the
release page; keep temporary handoffs outside the public source tree.
