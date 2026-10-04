# Manual Windows publisher

Run from a complete AI Nexus checkout. The renderer and logo have one authoritative
source in `services/birdynator/`; the publication helper is in `deploy/journal-host/`.
Python 3 and Windows OpenSSH are required. The script can find the bundled workstation
Python runtime, or accepts `-PythonExe`. It never saves passwords or private keys.

Connect the existing WireGuard profile, then invoke:

```powershell
.\Publish-Journal.ps1 -AnalysisId 13 -AiHost AI_HOST -UtilityHost UTILITY_HOST
```

Replace the symbolic SSH aliases using your existing private SSH configuration.
Optionally supply `-JournalUrl` for the final message. No live destination is built
into this source. Use a process-scoped execution policy when required by the local
Windows policy; do not weaken machine-wide policy to run this tool.

`-ReadOnly` saves the requested record without publishing. Otherwise the script
renders, creates a private Utility staging directory, uploads and requests sudo
publication. It does not trigger a model run. Repeating a saved ID updates its entry.
Private records and generated pages live under the ignored `private/` directory.
Rendered JSON/evidence is readable by LAN Journal readers; raw records stay local.
Retained releases and staging have no automatic cleanup. See the Journal chapter
and hosting instructions for validation and recovery.
