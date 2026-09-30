# Repository updates and public hygiene

## Keep deployment and publication distinct

The AI host checkout, a review workstation checkout and the remote repository can
be at different revisions. Copying a deployment bundle changes files; it does not
commit or publish them. A container build's `COMMIT` line is not a Git commit.

Run Git commands from the checkout. A subshell such as `( cd ...; ... )` returns
to the original directory when it exits; a later “not a git repository” message
from the home directory does not imply that the repository was lost.

Review status and recent history before continuing an interrupted update:

```bash
git status -sb
git log -1 --oneline
git --no-pager diff --stat
git --no-pager diff --cached --stat
```

An `ahead` count compares against the locally cached remote-tracking reference,
which may be stale. Review `git log --oneline origin/main..HEAD` before pushing;
do not assume every listed commit is absent remotely. Confirm publication from a
successful push result. Fetching/pulling is remote access and follows the applicable
approval policy. Do not pull over unexplained local changes or force-push to solve
a rejected update.

## Review the exact change

Stage explicit intended paths, including new files; avoid adding diagnostic logs,
archives or unrelated changes. Review the staged content, then run:

```bash
git --no-pager diff --cached --check
make repo-check
```

`make repo-check` is a tracked-file syntax/content scan. It does not inspect Git
author/committer metadata, untracked files, all possible secrets, or runtime health.
Manual public-hygiene review is still required. For application changes, also run
`make test`, the relevant update workflow and deployed `make verify`. Documentation
changes alone do not require a container rebuild or a paid model rerun.

When the session requires approval before remote Git access, commit or push, obtain
it before those actions. Do not represent another model's review as completed
unless it actually occurred.

## Windows/Linux line endings

Files transferred from Windows can contain CRLF or mixed line endings even when
a workstation's Git settings normalize its own diff. Linux `git diff --check`
may report `^M` as trailing whitespace across otherwise unchanged lines.

Normalize only the explicitly reviewed text files to LF; preserve Makefile recipe
tabs. Restage those paths and rerun the staged diff check and relevant tests.
Do not suppress the whitespace check or normalize the entire repository blindly.
Verify LF in the actual transfer archive, not just the workstation Git diff.

## Public author and committer metadata

Git can infer attribution from the local account and host when identity is not
configured. That can disclose private topology even when file-content checks pass.
Set an intentional public identity before the next commit. Replace both placeholders
with the chosen public values (for example, the account's actual GitHub-provided
no-reply address); do not copy a private machine-generated address:

```bash
git config --local user.name "PUBLIC_AUTHOR_NAME"
git config --local user.email "PUBLIC_COMMIT_EMAIL"
git config --local user.useConfigOnly true
git var GIT_AUTHOR_IDENT
git var GIT_COMMITTER_IDENT
```

Inspect the last two outputs locally before committing. Environment variables and
author/committer overrides can supersede these settings. Attribution settings do
not change SSH authentication or repository access.
[Git configuration reference](https://git-scm.com/docs/git-config).

After committing, review `git log -1 --format=fuller` privately. Changing Git
configuration affects future commits; it does not remove metadata already
published. Any history rewrite needs a separate, explicit decision and coordination
with other checkouts. Do not amend and force-push automatically.

## September 2026 publication record

The operator's terminal output confirms Birdynator commit `798cad6` was pushed to
`main`, followed by a clean checkout synchronized with its remote-tracking branch.
The push advanced the remote from `b436655`; the earlier local `ahead 6` display
was therefore not evidence that six additional commits still needed publication.

The same output showed automatically inferred committer attribution. Its live
value is intentionally omitted here. Configure intentional public attribution
before future commits; published-metadata remediation remains a separate decision.
