# Personal journal login and queue recovery

The browser login controls review saving/history only. It does not control
Utility SSH, sudo, reading the journal or AI Nexus. Administration is the recovery
path; there is no hidden unauthenticated feedback endpoint.

## When sign-in fails

Keep the queued reviews and reviewer UUID. Check the public HTTPS page first.
A certificate warning is a trust/expiry issue, not a password failure. Confirm the
login username is `personal` and the journal login password comes from its own
password-manager item, not the authority or Utility administration item.

Through the existing named-account Utility SSH connection, inspect:

```sh
sudo nginx -t
sudo systemctl status journal-feedback.service --no-pager
sudo journalctl -u journal-feedback.service -n 30 --no-pager
```

Keep raw diagnostics private. The service deliberately avoids logging credentials
and review bodies. HTTP 401 points to authentication, 429 to the rate limit,
503 to temporary storage availability, and 507 to the storage admission guard.
Do not repeatedly resubmit an ambiguous save; the browser retries the same UUID.
After a restart, re-check the private socket and queue ownership before changing
permissions. Never fix access by making the socket, password file or queue public.

## Password reset

Password reset remains an explicitly approved maintenance operation, not an
installed self-service endpoint. Use the existing SSH/sudo access to replace only
the `personal` password hash in the root-controlled nginx password file. Enter a
new password interactively through a reviewed helper; never put it in a shell
argument, terminal transcript, source file or chat. Preserve a root-only backup
of the old hash file before replacement and validate nginx afterward.

Keep the login-to-reviewer mapping in private service configuration unchanged.
Password rotation must not create a new reviewer UUID or change saved reviews.
Close/reopen the browser session if it retains old Basic credentials. The queue
and import receipts remain intact. A safe reset helper still needs preparation
and verification before an actual reset is requested; these notes are not a
tested reset command.

## Temporarily pause feedback

After approval, stopping `journal-feedback.service` pauses saving/history while
the journal remains readable. Disable the unit too if the pause must survive
reboot. Reading is served independently by nginx. Reviews are not deleted.
This leaves the protected API returning an outage; removing the UI/route cleanly
also requires a reviewed publication/nginx change.

The activation recovery directory retains the prior HTTPS configuration and
receipt. Restore it only after verifying that no subsequent approved nginx changes
would be overwritten. Remove only the rate-limit configuration owned by feedback,
then run nginx syntax checks and reload. Do not run the original installer against
an existing account, queue or receipt.

## Queue recovery and backup

The queue is private persistent state, separate from application files and journal
releases. Use the prepared SQLite backup API for a consistent snapshot while saving
continues, then retain a private off-VM copy. An on-VM initial snapshot alone does
not protect against VM loss. Back up service reviewer mapping with it; handle the
password-hash file as sensitive administrative material.

Restore is a separate reviewed procedure with the service stopped, private owner
and modes restored, and schema/version/integrity checked. Preserve original files
and imported receipts. A restored snapshot may contain reviews already imported
into AI Nexus; stable UUID/hash receipts make deliberate replay idempotent once
the SQL/transport stage is installed. Never acknowledge a queue item merely because
it was exported or a transfer appeared successful.

Canonical memory and source observations are outside feedback recovery. Review
restoration must not promote hypotheses or user comments into those stores.
