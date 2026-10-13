# AI Nexus

AI Nexus runs isolated AI agents in a home lab. Its first agent, **Birdynator**,
turns BirdNET observations into an evening Journal: what changed, which species
account for it, and what is worth watching next.

The useful distinction is between observations and interpretation. BirdNET owns
the source observations; Birdynator computes comparisons and saves its generated
reports separately. A classifier label or an interesting story is not automatically
an accepted fact.

## Current state

The October 12 repository inspection confirmed a clean AI Nexus checkout at
`415eda0`. The baseline Journal prompt is `birdynator-narrative-v3.0`, using
`gpt-6.1-sol`. An approved species-history trial uses v3.2-trial from October
13–19 at the existing 21:00 Pacific schedule; the baseline resumes October 20.
Publication to the Journal remains manually triggered from Windows.

Utility's HTTPS reading site and personal feedback queue are installed and
operator-tested on Windows and Android. Their source is prepared in this update;
AI Nexus feedback import and PostgreSQL schema are **not installed**. Reviews do
not automatically change prompts, train models or enter canonical memory.

See [Birdynator releases](docs/birdynator-releases.md) for release identity,
features and the distinction between Git, installed code and prompt versions.

## Read an evening chapter

| Start with | What it explains |
| --- | --- |
| [Project overview](docs/executive-summary.md) | How the pieces fit together and why they are separate |
| [The Journal's journey](docs/birdynator-journal.md) | From a recorded observation to the page you read |
| [Analysis](docs/birdynator-analysis.md) and [trial](docs/journal-trial.md) | Comparisons, uncertainty and evaluating better stories |
| [Reader feedback](docs/journal-feedback.md) | Saving reviews today and the proposed improvement cycle |
| [Architecture](docs/architecture.md) and [security](docs/security-baseline.md) | Where trust is granted and enforced |
| [Recovery](docs/backup-recovery.md) | What survives failure and how restoration is checked |

Each chapter links to implementation and operating details. The
[decision log](docs/decisions.md) preserves dated reasoning; older entries describe
their own point in time rather than overriding current status.

## Where the implementation lives

- `services/birdynator/`: evidence, prompts, analysis persistence and shared renderer.
- `services/journal_feedback/`: Utility collection, review contract and proposed importer.
- `clients/windows/journal/`: manual publication and local certificate preparation.
- `deploy/journal-host/`: Utility nginx, HTTPS and feedback service installation.
- `containers/`, `scripts/`, `migrations/`: AI Nexus runtime and operating workflows.
- `proposals/`: designs awaiting validation and approval; not automatic migrations.
- `tests/`: offline regression checks; live verification is a separate operation.

## How isolation works

AI Nexus is a Debian VM behind OPNsense, managed through WireGuard. Rootless
Podman runs Birdynator with no host-published port. Dedicated proxies grant the
OpenAI API and read-only BirdNET datasource paths; PostgreSQL and embeddings stay
on internal networks. Host nftables adds another enforcement layer.

Windows carries saved reports to the separate LAN Utility VM. Utility does not
join the AI bridge or receive AI database credentials. Its feedback queue accepts
narrow authenticated HTTPS requests; the proposed return path also goes through
Windows. See [network](docs/network.md) and [runtime](docs/agent-runtime.md).

## Work safely

`make test` runs offline Python tests; `make repo-check` checks tracked syntax and
public-repository hygiene. Feedback browser tests use
`node tests/test_journal_feedback_browser.cjs`. These do not verify a live host.

`make birdynator-update` applies pending migrations, rebuilds/restarts Birdynator
and verifies its paths. `make verify` checks the full deployed runtime and needs
live dependencies. Neither is a documentation-only step. Platform bootstrap is
not a complete one-command reconstruction of every service.

Follow [repository workflow](docs/repository-workflow.md) before publishing and
[reproducible runtime](docs/reproducible-runtime.md) before deploying. Keep secrets,
private addressing, raw reports and operator receipts out of this public repository.
