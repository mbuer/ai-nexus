# A daily report, with publication under your control

The two operations have different responsibilities. AI Nexus generates and retains
one daily interpretation. Your Windows PC later carries saved reports to Utility.
Closing the PC or disconnecting WireGuard does not stop generation on AI Nexus;
it merely postpones publication until you choose to sync. Utility never needs access
to the AI bridge.

## Manually sync every missing report

With the existing WireGuard profile connected, run the Windows publisher:

```powershell
.\Publish-Journal.ps1 -SyncNew -AiHost AI_HOST -UtilityHost UTILITY_HOST
```

Keep real SSH aliases and addresses in private operator configuration. The command
first reads Utility's published report IDs, then reads missing completed BirdNET
analyses from AI Nexus in a read-only transaction. It renders and publishes batches
of up to 250, preserving the existing archive and release history. It continues
through complete batches until the final saved-analysis snapshot is exhausted.
A sync with nothing new makes no upload. Analyses saved after the final query
are picked up by the next manual sync.

The client builds the index and copies the logo once per batch. Uploads use short
relative page paths to stay within the Windows command-line limit. A final batch
with fewer than 250 records completes without another SSH login; a full batch
requires another query to check for more records.

The first sync can bring in older saved trials that were never published; it imports
all missing saved BirdNET analyses, not only scheduled runs. One date can therefore
have multiple existing report IDs. It does not fabricate new historical analyses,
rewrite saved prose, or generate a report. Older rows without matching evidence
keep their legacy text without invented charts.

After a failed attempt, rerun the command when the problem is resolved. It reads
Utility's inventory again instead of trusting a local last-success counter, so
completed batches are not duplicated. Raw records and batch files stay under the
ignored client `private/` directory. Published JSON/evidence is visible to LAN readers.
Cleanup remains manual. Deliberately updating an already published report's layout
still uses the existing `-AnalysisId` mode; `-SyncNew` only handles missing IDs.

Password and sudo prompts remain interactive. No scheduled Windows task, new key,
stored password or unattended publication account is introduced.

## Generation at 9 p.m. Pacific

The installed user timer runs at **21:00 America/Los_Angeles**. This is a fixed evening
time, not a measured sunset or a guarantee that every bird is asleep. It summarizes
the latest available rolling 24 hours against the preceding 30-day baseline,
including any nighttime detections. Source-hour availability can lag the clock;
the saved source window remains the authority for the report's scope.

The timer calls `scripts/daily-journal.py` on the host. That script invokes the
existing restricted container and controlled proxies with the normal analysis CLI.
It does not move credentials onto the host or expand container networking. Optional
species research is enabled through the existing approved enrichment policy and
model routing; it can incur the normal daily API cost.

The installer sets a private `not_before` date to tomorrow in Pacific time. It enables
the timer without starting the generation service. This preserves the operator's
request for no additional report today. The worker also enforces that start date,
even if someone manually starts its service too early.

Before requesting a report, the worker checks for any saved BirdNET analysis created
on the current Pacific calendar date. A manual saved run counts too. If one exists,
the worker makes no new request. A host-side lock prevents two instances of this
worker from running together. Independent manual analysis commands are outside
that lock and should not be launched concurrently with the scheduled job.

An attempt receipt is written before the model command. If generation fails or the
outcome is ambiguous, the worker will not request another report that date. On a
later inspection it checks the database first, so a run saved before an interruption
can be recognized. These safeguards limit duplicate automated attempts; they do not
make a distributed model/database operation exactly-once.

Missed generation days are not automatically reconstructed. `Persistent=false`
avoids an immediate timer catch-up after restart, and failed runs have no automatic
retry. A suspended VM can still resume a pending calendar event; the date and attempt
guards continue to apply. Manual sync catches up on reports that were actually saved.
See the official systemd [timer](https://github.com/systemd/systemd/blob/main/man/systemd.timer.xml)
and [calendar](https://github.com/systemd/systemd/blob/main/man/systemd.time.xml) references.

## Installation and inspection

Operator output on October 3 confirmed the timer enabled and active after the
Quadlet validation fix. Its private start guard is October 4, so the October 3
calendar wake requests no analysis. The first eligible generation is October 4
at 21:00 Pacific. A completed scheduled model run has not yet been verified.
The source update and timer fix were published as `2834f26` and `769c2b8`.

### Which reports appear on the homepage

The homepage shows one report per report date: the saved report with the highest
numeric analysis ID. No specific dates or IDs are hardcoded. The report date comes
from the saved source window, rather than the publication date. Republishing an
older report does not make it the latest version.

Earlier versions remain in the database and published archive, including their
HTML, Markdown and JSON files. The Markdown index lists all retained versions;
the homepage is a reading view, not the complete inventory. Sync checks the complete
published inventory, so hidden versions are not repeatedly uploaded.

A later experimental analysis for the same source date will replace that day's
homepage entry once published. This rule does not distinguish approved reports
from prompt experiments. If experiments become routine, introduce an explicit
published-version selection rather than treating the highest ID as approval.

After the source update has been checked on AI Nexus, use the existing non-root
operator account:

```bash
python3 scripts/install-daily-journal.py --time 21:00
systemctl --user list-timers ai-nexus-daily-journal.timer --no-pager
```

The installer requires the existing user lingering setup, validates the calendar and
unit definitions, retains copies of existing installed files, and enables only this
user timer. It does not rebuild Birdynator or generate an analysis at installation.
Unit validation invokes user generators so the existing Podman Quadlet services
are available as dependencies. Without this, the independent verifier can report
a missing Birdynator service even while the user manager runs it successfully.
See the systemd [verification options](https://github.com/systemd/systemd/blob/main/man/systemd-analyze.xml).
The runtime copy is under the operator's local libexec directory; private config,
attempt receipts and installation recovery copies are under local state. Updating
the repository later does not automatically change that installed copy: rerun the
installer as part of a reviewed update. Unrecognized existing files cause refusal.

Inspect the next scheduled run and its outcome:

```bash
systemctl --user status ai-nexus-daily-journal.timer --no-pager
journalctl --user -u ai-nexus-daily-journal.service -n 60 --no-pager
podman exec agent-birdynator python /app/birdynator.py analysis-history --limit 3
```

For a failed or uncertain attempt, inspect those logs and the saved analysis history
before deciding on a deliberate retry. Do not blindly remove the receipt and rerun.
No alerting or automatic notification channel is configured in this initial design.

To pause future generation:

```bash
systemctl --user disable --now ai-nexus-daily-journal.timer
```

This stops the schedule; it does not cancel an already running model request or
delete saved reports. Re-enable the timer when desired. Publication remains manual
through the same Windows sync command throughout.
