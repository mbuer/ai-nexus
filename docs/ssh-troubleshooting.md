# SSH management reliability

## Current status

As of the September 30, 2026 review, intermittent management SSH resets remain
unresolved. Connections currently work again; no durable fix or root cause has
been demonstrated. Investigation resumes on recurrence, without speculative
configuration changes while the path is healthy.

This is the current investigation record and recurrence procedure. See
[Management access](management-access.md) for the intended configuration and
[the September 23/24 record](troubleshooting-2026-09-23.md) for the original history.
Security controls and application runtime checks have passed; those checks do not
establish sustained reliability of the management connection.

## Evidence and scope

This review uses operator-provided terminal excerpts, available project chat
excerpts and repository records. Complete early chat history and original packet
captures were not available for reinspection. Distinguish recorded historical
conclusions from raw evidence reproduced in a new investigation.

All names below are symbolic. Keep raw logs, packet captures and configuration
exports outside the public checkout. Do not attach them to public issues without
redaction.

## Investigation history

| Investigation | Recorded result | What it establishes |
| --- | --- | --- |
| Direct LAN management using a Windows static route through OPNsense | Connected, then reset; approach abandoned | It did not provide reliable management and is not the intended path |
| Firewall permission, ordinary MTU failure, OPNsense routes/ARP, Proxmox bridging and sshd as reset origin | Earlier notes described these as ruled out | Conclusions belong to those tests; original captures are not available here and the current tunnel path is different |
| `reply-to` and force-gateway experiments | No lasting fix | Do not reintroduce these settings without new evidence |
| Capture on the direct-LAN path | Retransmissions followed by a TCP reset attributed to Windows | Identifies a reported reset source for that capture, not the reason for preceding loss or the source of today's tunnel failures |
| Home WireGuard profile initially reusing the Away identity | Initial success followed by resets; tunnel restart temporarily restored access | Peer reuse was an ambiguity worth removing, not a proven sole cause |
| Dedicated Home peer, unique keypair/address, local endpoint, keepalive | Correct peer/source and handshake activity verified; resets recurred | Keep separate Home/Away peers; the change did not resolve reliability |
| GitHub SSH moved to TCP/443 | Outbound Git access worked without broadly opening TCP/22 | A separate AI-host-to-GitHub connection, not a fix for management SSH |
| September 29 native Windows terminal attempts | Resets, connection aborts, successful logins, and later reported session losses | The failure is not confined to an agent execution environment |
| Server SSH journal | Public-key and password authentications accepted; one session closed about a second after opening | Authentication worked on those attempts; the excerpt did not establish why the session closed |
| Separate failed authentication sequence | Password rejection followed by “Too many authentication failures” | A specific authentication failure; do not merge it with every transport reset |
| VM reboot, later PC reboot and retries | Access returned at times; no controlled durable resolution | Recovery is not proof of root cause |

The earlier planned next step was to capture outer WireGuard traffic while the
failure persisted. No completed, correlated result for that step was available
in the reviewed material.

## Distinguish failure classes

1. **Before authentication:** cannot establish TCP, connection aborts, key exchange
   fails, or the server disconnects before login completes.
2. **Authentication rejected or timed out:** explicit key/password rejection,
   authentication-limit message, or a server-recorded login timeout.
3. **After authentication:** the shell/banner appeared or the server accepted
   authentication, and the session subsequently closed or became unresponsive.

A local key passphrase unlocks the private key on the client. A server account
password is a separate authentication method. Seeing both prompts means fallback
was attempted; the prompts alone do not establish why key authentication failed.
Ordinary terminal paste artifacts likewise do not establish a network diagnosis.

The recorded server policy includes `LoginGraceTime 30` and `MaxAuthTries 3`.
The former bounds time to authenticate and the latter limits authentication
attempts per connection. They are candidates for some login-stage symptoms,
not explanations for loss of an already authenticated session. Current versions
of OpenSSH also support connection limits and per-source penalties; their effective
settings and actual involvement on this host remain unverified. Consult the
installed manual and effective configuration before interpreting them.
[OpenSSH server configuration reference](https://man.openbsd.org/sshd_config).

## On recurrence: preserve one failure

Do not immediately reboot the VM/PC, cycle WireGuard, or repeatedly reconnect.
Record the time including UTC offset, active Home/Away profile, physical network
(home/away, Wi-Fi/Ethernet), and whether an existing session dropped or a new one
failed. Keep any working session open. Use the Proxmox guest console for independent
server access when SSH is unreliable; routine diagnosis uses the non-root admin
account and narrow `sudo` commands.

Use the configured local SSH alias in place of `AI_SSH_ALIAS` below. These examples
collect evidence only; they do not change firewall, SSH or tunnel policy.

### Windows PowerShell

Run these in a Windows terminal, not inside the remote Linux shell:

```powershell
Get-Date -Format o
ssh -V
ssh -G AI_SSH_ALIAS |
  Select-String '^(hostname|user|port|identityfile|identitiesonly|proxycommand|proxyjump) '
$sshLog = Join-Path $env:TEMP ("ssh-diagnostic-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")
ssh -vvv -E $sshLog -o ConnectTimeout=10 AI_SSH_ALIAS
# After SSH exits, back at the PowerShell prompt:
Get-Date -Format o
Get-Content -LiteralPath $sshLog -Tail 100
```

Record the selected route/interface to `AI_HOST` and the WireGuard handshake age
and send/receive counters in the same interval. Do not export the full tunnel
configuration, which contains private keys. A successful debug connection is a
healthy comparison sample, not a capture of the failure.

### AI host through the guest console

```bash
date --iso-8601=seconds
uptime
systemctl --failed
dpkg-query -W openssh-server
sudo sshd -T | grep -E '^(logingracetime|maxauthtries|maxstartups|persource|pubkeyauthentication|passwordauthentication|authenticationmethods|clientalive|channeltimeout|unusedconnectiontimeout)'
sudo journalctl -u ssh --since '15 minutes ago' --no-pager
```

Run close to the failed attempt, or select the exact recorded incident window.
Absence of a directive in this output does not establish a particular default or
that the feature is supported. If `Match` blocks apply, evaluate `sshd -T -C` for
the actual user and connection tuple privately; a general dump may not include
those connection-specific settings. Preserve relevant kernel/interface errors
from the same interval if present. Do not change server log verbosity as a first step.

### Correlate the packet path

Before another controlled attempt, arrange short, narrowly filtered captures:

| Observation point | Traffic | Question |
| --- | --- | --- |
| Windows tunnel side, where supported | Inner SSH TCP to `AI_HOST` | What did the client send and receive? |
| OPNsense endpoint-facing interface | Outer WireGuard UDP for the active peer | Does encrypted traffic flow both ways during the failure? |
| OPNsense WireGuard and AI interfaces | Inner SSH TCP for the same connection | Does the traffic pass between the tunnel and the AI segment? |
| AI host | SSH TCP for the same peer/connection | Do requests arrive, replies leave, or a reset originate here? |

Use the configured port and interface names, not assumptions. The documented
Home endpoint uses the OPNsense LAN side; Away requires observing its actual
external endpoint path. Compare clocks/offsets, TCP sequence numbers,
retransmissions and the first observed reset. Outer UDP packets alone do not prove
successful decryption or delivery of inner SSH traffic. A fresh handshake alone
does not prove a healthy SSH data path. Absence from one capture requires checking
the capture interface, filters and drops before concluding packet loss.

Save WireGuard handshake age/counters and relevant firewall pass/block/state
observations for that same interval. Collect one failure before changing anything.

## Interpretation and next change

- Authentication timeout/rejection/penalty in matching server logs: investigate
  that mechanism separately from authenticated-session loss.
- TCP visible at one point but not the next: localize loss using both directions
  and verify the capture setup before blaming a device.
- Reset observed: establish where it first appears and what preceded it; a source
  address alone does not establish the underlying software or network cause.
- No failure reproduced: retain the healthy sample and wait. Do not mark resolved.

Only then choose one bounded comparison, such as a second client with its own
authorized peer or a controlled interface comparison. Do not reuse a live peer
identity simultaneously on another device. Do not add direct-LAN bypasses, broad
firewall openings, or speculative MTU/authentication changes. The symptom predates
the latest observed kernel update; a version change is not itself evidence of a
regression. Successful SSH to another LAN service does not validate the AI path.

## Public incident record

Publish a sanitized summary containing date/window, symbolic path, symptom class,
capture points, findings, counterevidence, one tested change, its result and
remaining uncertainty. State whether evidence is a direct log/capture or an older
summary. Preserve useful ordering and durations without publishing raw identifiers.

Remove live IPs/subnets, WAN endpoints, DNS names, MACs, account names, key material
and fingerprints, local paths, VM/job/boot identifiers and session-specific
identifiers. Review screenshots and Git attribution as well as file contents.
Raw captures can contain unrelated traffic; retain originals privately and share
only the minimum redacted excerpt. See [Repository workflow](repository-workflow.md).
