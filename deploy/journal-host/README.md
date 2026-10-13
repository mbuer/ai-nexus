# Journal hosting and review collection

Utility remains on the home LAN. Do not attach it to the AI bridge. It needs nginx,
Python 3 and the existing administrator SSH/sudo path, not agent or database credentials.
This component is deliberately a manual administrator workflow.

For an existing site, inspect its listener, root, content policy and firewall first.
The symbolic nginx template describes the intended IPv4 LAN listener, GET/HEAD
access, same-origin logo and content restrictions. Substitute live values only in
an ignored private copy; it is not directly installable and was not compared with
a fresh live configuration dump. Preserve any unrelated sites.

For a new host, install nginx and Python using the normal OS package workflow,
create `/srv/birdynator-journal/current` as an initial directory with an index page,
and install a private copy of the template as a dedicated enabled site. Run
`sudo nginx -t` before reload. Permit only intended LAN readers to the chosen port
in the host firewall, preserving administrative access and existing services.
Same-LAN traffic does not traverse OPNsense. Do not add WAN forwarding.

The Windows tool copies `publish_utility.py` into a private upload stage and invokes
it through sudo. The helper validates names, ownership, size limits and checksums,
builds a completed release and replaces the current symlink. It retains the initial
site on first conversion, older completed releases and upload staging. It may add
the narrowly scoped same-origin image policy to an older Journal nginx site; this
backs up configuration, tests syntax and reloads with configuration rollback on failure.

For content rollback, inspect the retained `releases/` directories, choose a completed
release and verify it belongs under the Journal root. As the administrator, create
a temporary symlink beside `current` to that selected release, then use `mv -Tf`
to replace `current` atomically. Do not delete the current release first. Test the
HTTP response afterward. Restore a retained nginx configuration separately if
needed, running `nginx -t` before reload. Preserve an external backup of important
published material; same-host release history is not a disaster-recovery backup.

Automatic retention and a restricted unattended publishing account are not implemented.
Do not delete releases, upload staging or configuration backups until their recovery
value and any active publication have been checked.
## Feedback operations

HTTP/HTTPS reading and personal feedback collection live on Utility; the host has
no AI Nexus connection. The operator has verified HTTPS, login/status and feedback
across PC and Android. AI feedback import remains an unapproved proposal.

`feedback_config.py` is the canonical renderer for authentication/status nginx
routes. There is no second hand-maintained commented copy. Initial installation,
guarded resume, UI update and certificate renewal retain separate bounded recovery
paths because they operate on different existing states. Completed installers are
not routine launchers: inspect receipts before retries.

See the [feedback guide](../../docs/journal-feedback.md),
[recovery guide](../../docs/journal-feedback-recovery.md) and
[HTTPS plan](../../docs/journal-https-plan.md) for maintenance and release gates.
