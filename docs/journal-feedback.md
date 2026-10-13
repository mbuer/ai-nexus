# From an evening review to a better Journal

## Status and purpose

Source work began against commit `415eda0`. Operator output confirms Utility
HTTPS, personal sign-in, private queue and account-status UI installed. Report 23
was generated as a manual candidate preview and published with feedback enabled;
the operator confirms the feedback works on PC and Android. The October 13-19
scheduled Journal trial remains unchanged. No feedback SQL migration/import,
feedback repository commit or push has occurred. The later Utility/client cleanup
was installed successfully, preserving credentials, queue and structured reports.

The reader wants worthwhile evening reading and a long-term improvement cycle.
Start with personal reviews, while preserving separate reviewer identities for
future readers. Multiple devices belonging to one person are not multiple votes.
Reviews express preferences and concerns; they do not verify species identity,
recorder coverage, causality or scientific accuracy.

## One place to save, from any device

Browser local storage lives in one browser profile on one device. It would require
export/import to move feedback between a phone, PC and different browsers. The
preferred design is therefore a central durable outbox on Utility. A Save button
should acknowledge storage only after the review transaction has committed.

Utility remains independent of the AI network. It accepts narrow authenticated
LAN feedback requests, stores them privately, and has no AI Nexus connection or
credentials. The Windows PC carries bounded batches over its two existing SSH
paths in the planned feedback-transfer workflow. AI Nexus will validate and import
them into its editorial store after schema/transport approval and verification.
Windows will return exact import receipts to Utility. This transport is not yet
installed; current journal sync does not import reviews. Original
review records survive acknowledgments; retention is a separate explicit policy.

```text
Reader device -- authenticated HTTPS --> Utility feedback outbox
Windows PC   -- existing LAN SSH ------> export pending reviews
Windows PC   -- existing WireGuard SSH -> AI Nexus import
Windows PC   -- existing LAN SSH ------> acknowledge matching receipts
```

No browser or Utility service connects to AI Nexus. No new public endpoint, WAN
port forwarding, datasource grant or AI bridge attachment is part of this design.
The existing journal serves static reading material; only the reviewed feedback
route would accept writes. The write service must not write published journal
files, interpret commands, generate analyses or proxy arbitrary destinations.

## HTTPS and personal identity

Utility's existing nginx terminates HTTPS on its reserved LAN address. A dedicated
private authority was created with approval and trusted on reader devices. Its
encrypted signing key/backup stay on Windows and in the password-manager backup;
only the server pair and public authority were uploaded. See the HTTPS maintenance
plan for renewal responsibilities. No warning bypass or public-domain dependency
is part of the reading or review workflow.

One approved personal review login over HTTPS maps server-side to a stable
pseudonymous reviewer UUID. The separate password is managed by the operator.
Future multi-reader accounts need explicit approval.
Do not reuse SSH keys/passwords as browser credentials. Browser-supplied reviewer
IDs are checked against the authenticated mapping, never accepted as proof.

The installed service uses a private Unix socket behind nginx, exact same-origin
checks, JSON-only requests, small body/time limits and no cross-origin access.
Only the review save/read routes receive proxy access. Keep LAN address binding,
host firewall restrictions, no public exposure, and separate outbox permissions.
The static page needs one reviewed same-origin script allowance and same-origin
connections; no inline scripts, external CDNs or general network permission.
Feedback comments render as text. These collection controls were installed and
verified; the AI import proposal remains a separate release gate.

References: nginx [HTTPS](https://nginx.org/en/docs/http/ngx_http_ssl_module.html)
and [authentication](https://nginx.org/en/docs/http/ngx_http_auth_basic_module.html).

## Exact report identity

Each `journal-feedback-v1` event has a random canonical UUID, a stable reviewer
UUID, a client UTC timestamp, optional superseded-event UUID, and an exact target.
The target retains analysis ID, model, prompt version (including explicitly unknown
legacy values), source cutoff, source evidence digest and a SHA-256 of the original
saved narrative. A layout refresh need not invalidate a review of the same prose.
An evidence/model/prompt/prose change does. A review is never attached merely to
the report date or whatever report happens to be newest on the homepage.

The immutable body contains overall worth-reading feedback, issue tags, a comment,
what the reader wanted instead, and optional named-section reviews. Reading ratings
are `yes`, `partly`, `no` or `unsure`, not an invented numerical accuracy score.
Tags include repetition, support concerns, clarity, interest, missing context,
identification concerns and useful material. A support concern is a request to
check evidence, not an accepted correction. Raw quotations/comments are data.

The Python contract rejects unknown fields, duplicate JSON keys, invalid UUIDs,
non-finite values, boolean analysis IDs, duplicate sections/tags, empty reviews,
naive client times and oversized payloads. It canonicalizes UTF-8 JSON for a
stable payload digest. Schema versions permit later compatibility changes.
Client clocks remain untrusted; server receipt/import times determine transport
ordering. The proposed AI importer must verify the target against its saved
analysis again; that database-side path is not installed yet.

## Durable queue and retry behavior

`services/journal_feedback/outbox.py` prepares a SQLite outbox behind a future
service. It is not currently reachable by HTTP. Transactions use durable writes,
private file permissions and parameterized statements. Sequence order preserves
original-before-revision delivery even if clocks change. Indexed, bounded pending
batches and reader/report history avoid loading the entire feedback collection.

Saving the same UUID and body returns its existing state. Reusing a UUID with
different content rejects the request. A changed opinion creates a new event
which may explicitly supersede the previous one. The reader and exact target
must match. Concurrent forks of a revision are rejected so that a device with
an old view must refresh rather than silently overwrite another device's review.

If Windows disconnects after importing but before acknowledgment, the next
attempt replays the same event and receives an `already_imported` receipt with
the original import time. A matching receipt marks the Utility record imported;
it does not erase it. Wrong hashes, IDs or changed receipt times are rejected.
No timeout, a missing output line, or an empty batch proves that data was imported.

Use statuses such as draft in this browser, saved on Utility, and imported into
AI Nexus. Drafts are not cross-device until saved. The page must never claim
an improvement was learned simply because a review was saved or transported.
Storage admission guards and consistent backup commands are implemented. Scheduled
monitoring, off-VM backup cadence and restore verification remain outstanding.
A same-VM initial snapshot alone is not a disaster-recovery backup.

## AI Nexus storage and authority

The draft at `proposals/journal-feedback/005_journal_feedback.sql` is not in the
automatic migration directory. It is a proposed migration, not applied or
live-validated. It creates a curated reviewer registry and append-only feedback
events linked by foreign keys to `analysis_runs`. Exact payload digests and
original bodies preserve provenance. Superseded reviews remain retained; unique
successor references reject conflicting revision chains. No source observation,
generated narrative or canonical memory is modified by an import.

An import function checks accepted reviewer identity and exact saved target,
serializes duplicate IDs, and returns a stable import receipt. A NOLOGIN
`journal_feedback_importer` role may execute only this function, not write tables
or memory directly. The existing administrator path can explicitly SET ROLE for
an operator-authorized import. No password or new agent capability is introduced.
The scheduled `birdynator` role receives no new feedback permissions in this phase.

The definer function has a restricted search path, qualified table references,
and revoked PUBLIC execution. The host importer performs the full versioned
contract validation before any SQL call. The database independently enforces
identity/target/revision integrity. Validate the migration on a disposable test
database before approval; offline Python tests do not certify PostgreSQL execution.
Review owner/role privileges and backup coverage as part of the migration gate.
See PostgreSQL [function security](https://www.postgresql.org/docs/16/sql-createfunction.html).

`scripts/import-journal-feedback.py` validates a private bounded queue export by
default. Only its explicit import flag calls the existing PostgreSQL container.
Comments enter SQL only as base64-encoded canonical JSON, never concatenated SQL
syntax. Each event has its own transaction; confirmed receipts stream separately.
A partial batch retains receipts for completed events and pending unconfirmed
events. These are editorial imports, not datasource writes or model requests.

## The improvement cycle

1. Collect reviews tied to exact reports and sections. Keep the current seven-day
   prompt fixed while reading; record changes of opinion explicitly.
2. Prepare a review summary with provenance. Distinguish reading preferences,
   suspected unsupported claims, missed comparisons, and presentation complaints.
   One reader/report is a review unit; repeated clicks or devices do not increase
   independent support. Missing reviews do not imply satisfaction.
3. Verify support concerns against original evidence. An automated classifier or
   model judge may nominate an issue, but cannot certify biology or source truth.
4. Write a bounded improvement proposal: concrete problem, feedback IDs, version
   diff, expected benefit, known risks, tests and rollback. This may change evidence
   selection, longitudinal comparisons, prompt wording or layout; do not assume
   every complaint calls for another prompt paragraph or extra ML.
5. Freeze a varied evaluation set: substantive, quiet, repetitive and incomplete
   coverage days. Replay identical source cutoffs and record evidence, request,
   model/prompt/code versions, enrichment provenance, usage and failures. Reserve
   later days for evaluation rather than repeatedly tuning on the same favorites.
6. Compare new and baseline versions. Prefer paired human review, optionally
   hiding which version is new. Check useful information, repetition, support,
   omission behavior, reading pleasure and cost. Length is not the objective.
7. Approve a bounded live trial with one attempt per day and an automatic return
   path. Preserve the baseline and exact candidate. Human acceptance is explicit.

Generated review summaries and improvement hypotheses belong in an editorial
experiment record, separate from both raw feedback and canonical memory. Future
experiment records should retain immutable plans, input IDs/digests, actual API
requests/results, comparison decisions and promotion/rollback events. A mutable
"current prompt" file alone cannot reconstruct why a release was chosen.

## How automation can grow

First automate safe collection, duplicate handling, transport and deterministic
review summaries. Next, explicitly authorize bounded model-assisted proposals
and replay jobs with cost/request limits and failure receipts. Later, allow an
approved controller to select candidates for a time-limited trial only after fixed
tests and review gates. Treat model judgments as advisory; raw comments must not
become privileged instructions or unrestricted agent tasks.

Permanent automatic promotion is a separate future authority decision. It would
need predetermined acceptance criteria, enough relevant human evaluation, quiet
day and coverage checks, operational monitoring, reproducible artifacts and a
tested rollback. Passing a prose judge or accumulating thumbs-up is insufficient.
Security, datasource permissions, factual definitions and canonical memory remain
outside any editorial optimizer's authority. Fine-tuning is not an initial goal:
first establish a useful review corpus and show that simpler changes help.

## Current remaining work and release gates

The locally prepared request-policy module validates authenticated reviewer
mapping, exact HTTPS origins, JSON/body limits, bounded reader-scoped history,
revision conflict responses and rejection of browser acknowledgments. A candidate
Linux Unix-socket adapter now preserves repeated headers, rejects ambiguous HTTP
framing and oversized/incomplete bodies, bounds connection time and worker count,
and forwards only nginx's authenticated principal. There is no TCP fallback.
The service candidate has private state, a socket accessible only to its account
and nginx group, no network namespace access and no elevated capabilities.
Saving pauses at 256 MiB of local state or below 32 MiB free disk, retaining all
existing reviews. This admission check is a guard, not a filesystem quota; reserve
space, monitor queue/acknowledgment age and plan private consistent SQLite backups
before production. Never silently delete unimported or superseded reviews.

Personal HTTP Basic authentication is the agreed initial login, over HTTPS only.
Use a separate journal password, never the CA passphrase or administration password.
nginx owns password verification; the service never receives the password or
Authorization header. nginx must overwrite Remote-User on the private socket path.
That socket group is a trust boundary, so unrelated accounts must not join it.
One immutable reviewer UUID maps the login across devices; more logins can map to
additional UUIDs later. Reading stays public within the existing LAN restriction.
Sign-in, history and saving share one authentication realm and API path prefix.
Browsers manage Basic-login caching; no application logout or account-registration
system is promised. Disable a login by removing its password-file entry under an
approved procedure; preserve its review history and UUID.

The panel remains static/disabled by default. An opt-in decorator binds the exact
raw saved narrative digest, appends a panel and allows only an external same-origin
script/API in the page CSP. Production nginx must independently allow them on
HTTPS only. Prepared browser controls load personal history, keep saved revisions
append-only and retain the exact pending UUID/body across uncertain saves. A
confirmed receipt remains success even if subsequent history loading fails.
Conflict responses retain the draft and require a fresh revision. Drafts remain
in the open tab only; confirmed reviews are centrally available across devices.
Rendering uses textContent for stored reviews, never interprets them as HTML.

Operator results confirm the installed Linux service, nginx authentication/status,
publication and feedback UI on PC/Android. Offline tests cover the contracts and
browser failure paths. PostgreSQL execution and end-to-end transport remain release
gates. Subsequent Utility/client optimizations were deployed with retained rollback files
and queue backup; full structured provenance and existing reviews were preserved.

- Reconcile the installed collection source with Git and review its final diff.
  Preserve queue/credentials during any update.
- Validate the proposed SQL migration and least-privilege import in a disposable
  database; complete transport crash/retry and receipt-handling tests.
- Add explicit feedback sync to the Windows launcher. Keep journal publication
  and feedback import visibly separate, even when launched together.
- Review backups, retention, account disablement, rollback, nginx/CSP changes and
  the final source diff. Obtain approval before commits, pushes, remote Git access,
  schema/privilege changes or later service deployment.

Use coherent commits: local HTTPS setup is distinct from the feedback feature;
feedback code, migration, tests and runbook belong together. No approval for this
design authorizes infrastructure changes. Keep private reviews, credentials,
certificates, live addresses and operator captures outside public Git.

## Utility collection rollout candidate

The first activation is deliberately collection-only. Its reviewed package creates
one non-login service account, root-owned application/configuration, a private
SQLite outbox and one `personal` browser login. The operator enters a separate
password interactively; OpenSSL SHA-512-crypt hashes stdin, never command arguments.
nginx alone reads the resulting restricted password file. The stable reviewer UUID
is retained in private configuration and recovery receipt.

The installer compares the complete existing HTTPS configuration hash before
editing it, runs nginx and systemd validation, verifies anonymous rejection,
authenticated reviewer mapping (including forged-header replacement), sign-in and
JS serving, HTTP API absence and unchanged plaintext journal configuration.
It exercises consistent SQLite backup creation before enabling the service at boot.
Failures stop the new service, restore HTTPS configuration and remove the owned
rate-limit file; credentials, code, account and queue remain for inspection.
Never automatically delete the queue or repeat a partially completed installation.

No AI Nexus schema, SQL import, Git operation, firewall rule or model request is
part of this collection stage. Reviews can accumulate safely on Utility while
the separate migration/transfer is verified. The UI states that transfer is pending.
The existing sync launcher does not yet import feedback.

After activation, publish an existing saved analysis with `-FeedbackEnabled`
(or future missing reports with `-SyncNew -FeedbackEnabled`). This decorates HTML
only, validates the raw saved narrative against the structured report and preserves
Markdown/JSON. Reports without complete identity cannot receive a review panel.
Publication does not generate a model analysis. Existing reports are updated only
when explicitly re-published; old release directories remain for recovery.
The opt-in flag must not be enabled before service/CSP activation succeeds.

Back up the queue via the operator-only `journal_feedback.queue_tools --backup`
command into a preprovisioned private directory, then transfer that snapshot to a
private off-VM location. Initial on-VM recovery alone is not an off-VM backup.
The backup API closes both SQLite connections explicitly and refuses overwrites.
The queue export/acknowledgment tools are not browser routes. AI import validation,
schema/grant testing, durable Windows transfer and a reviewed backup cadence remain
required follow-ups before claiming a complete feedback improvement loop.

Initial live activation stopped after nginx reload when its first anonymous
API check received 404 instead of 401. An asynchronous old-worker response is
plausible, not yet proven. The installer now retries only that 404 for at most
4.5 seconds; persistent errors or anonymous success still fail. A guarded resume
requires a clean rollback receipt, unchanged reviewed application/unit/config,
stopped disabled service, privately owned queue, matching HTTPS backup and unchanged
HTTP. It preserves the existing password and reviewer UUID; the password is entered
again solely for authentication checks. A changed tree or later incomplete phase
stops for inspection. Recovery receipts are preserved before resuming.

## Account visibility improvement candidate

The initial panel put its sign-in link inside collapsible feedback content. The
updated renderer places a permanent account strip above that fold. It shows
server-verified signed-in/signed-out state, checks again on focus after login,
offers a manual status refresh and distinguishes an unavailable check from a
confirmed sign-out. A slow old check cannot overwrite a newer authenticated save.
The link remains visible in either state. Only explicitly updated report pages
have this UI; existing unmodified historical pages do not gain it automatically.

A separate read-only nginx session location performs the same Basic verification,
then maps to the existing private context handler. Its own anonymous challenge
returns a signed-out JSON response instead of opening a browser login dialog.
This conversion applies only to that status location: saving and history still
require login, and the updater tests their anonymous rejection. Status checks have
a separate narrow rate limit and no cache. Passwords still never reach Python.
Server authorization remains authoritative; the displayed label grants no access.

The update compares installed nginx/JS hashes, preserves root-only recovery copies,
checks nginx syntax and reloads, tests the anonymous status and protected routes,
then requires report re-publication for the header change. It changes no credential,
reviewer UUID, queue, service process, firewall, AI source or SQL state. Browser
Basic caching and real nginx error handling remain live verification requirements.
