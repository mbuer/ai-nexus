# SSH management reliability

## Current status

On September 30, 2026, active firewall rules confirmed a gateway-forced return
path for Home WireGuard. A narrow per-rule exception was applied and a subsequent
capture verified direct replies to the client. This corrects an observed routing
problem; sustained reliability and attribution of every historical reset remain
unverified. Preserve the correction and collect evidence if failures recur.

This is the current investigation record and recurrence procedure. See
[Management access](management-access.md) for the intended configuration and
[the September 23/24 record](troubleshooting-2026-09-23.md) for the original history.
Security controls and application runtime checks have passed; those checks do not
establish sustained reliability of the management connection.

## Evidence and scope

This review uses operator-provided terminal excerpts, available project chat
excerpts and repository records. Complete early chat history and original packet
captures were not available for reinspection. New September 30 captures were
inspected directly for the follow-up below. Distinguish recorded historical
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

The earlier planned outer-WireGuard capture was completed during the September
30 recurrence; see the follow-up below.

## September 30 paired-capture follow-up

The VM console showed SSH active and port 22 listening while Windows recorded
connection timeouts before authentication. WireGuard logs showed repeated failed
handshake attempts and intermittent recovery. This establishes a tunnel-level
symptom in these incidents, not the cause of every historical SSH reset.

- A healthy firewall capture showed a handshake response and bidirectional
  encrypted traffic during a successful SSH login.
- A failing firewall-only capture contained 19 handshake requests, each with a
  matching response about 0.3–0.5 milliseconds later at that capture point.
- In the overlap of paired firewall and Windows captures, nine Windows handshake
  requests reached the firewall and received matching responses there. None of
  those nine response payloads appeared in the Windows capture. An earlier
  healthy response did appear in Windows. Packet payload matching accounted for
  roughly 0.86 seconds of clock offset between the capture points.

The observed gap lies between the firewall virtual LAN capture point and the
Windows physical-adapter capture point. It does not prove physical transmission
or identify the bridge, access point, adapter, driver or filtering component
responsible. Verify capture drops and interface selection before assigning cause.
Encrypted outer traffic does not explain key-to-password authentication fallback.

The client initially used Wi-Fi, then switched to Ethernet with Wi-Fi disabled
and the same Home WireGuard path retained. An apparent stall was reported before
access recovered; Git publication subsequently succeeded over Ethernet. This is
not proof of sustained wired reliability or that Wi-Fi caused the fault. No paired
wired-failure capture has yet been reviewed. Timing around Git commands is not
causal evidence: local identity commands do not contact a remote, and fresh SSH
attempts also failed before Git commands ran.

Next, capture both the Windows physical adapter and firewall LAN during another
recurrence, retaining capture-drop statistics and command timestamps. Compare
exact response payloads across the points. Keep the authorized Home peer and
isolation policy unchanged; spontaneous recovery is not a demonstrated fix.

## September 30 return-path correction

### Evidence and interpretation

The router vendor MAC was identified as HOME_ROUTER, not an unknown client.
Earlier failed handshake requests arrived with the client Wi-Fi source MAC, while
firewall replies targeted HOME_ROUTER and were absent from the paired Windows
capture. A later working capture used HOME_ROUTER's MAC in both directions.
Thus the router MAC alone did not distinguish success from failure.

Windows showed a directly connected route and the correct firewall neighbor MAC.
The firewall routing table also showed HOME_LAN directly connected. Proxmox shell
inspection showed its Wi-Fi down with no address; the LAN bridge had one physical
dock/Ethernet uplink. These observations did not establish a dock or Wi-Fi fault.
Earlier reported client Ethernet testing is inconclusive: the later adapter list
showed a virtual VPN adapter and the physical Ethernet adapter disconnected.

The decisive configuration evidence was the loaded packet-filter rules: both the
broad LAN allow rule and the existing WireGuard listener rule contained
`reply-to (LAN_INTERFACE HOME_ROUTER)`. LAN receives configuration through DHCP.
The rule editor's Gateway=None did not exclude an automatically generated reply-to.
This explains the gateway-directed replies despite a connected subnet route.
It is a strong explanation for the captured failure pattern, not proof that every
historical reset or key/password fallback had this cause. Why the router forwarded
some exchanges and not others remains unverified.

### Applied narrow change

A new rule, Home WireGuard direct replies, was placed before the broad LAN allow:

| Setting | Value |
| --- | --- |
| Interface / direction / action | LAN / in / pass |
| Quick | Enabled |
| Version / protocol | IPv4 / UDP |
| Source | LAN network; any source port |
| Destination | LAN address; listener port 51820 |
| Gateway / explicit reply-to target | None / None |
| Disable reply-to | Checked |
| State handling | Keep state |

The operator applied the rule and supplied loaded-rule output showing it before
the broad allow, with no reply-to clause. Existing broader rules retained theirs.
The instructed transition deactivated Home WireGuard, removed only the matching
Home UDP state if still present, and reactivated the tunnel; reconnection was
confirmed. No global state flush, DHCP/default-gateway change, global reply-to
disable, direct-LAN AI access or widened agent Internet access was required.
The Home source scope leaves the external Away path outside this exception.

### Post-change validation and remaining work

A directly inspected capture contained 1,000 packets over about 4 minutes 57 seconds:
527 client-to-firewall and 473 firewall-to-client. All frames used the client and
firewall MACs directly; none used the router MAC. Two handshake requests had
matching responses and encrypted data flowed both ways. The capture stopped at
its packet limit; it does not establish reliability beyond that interval.

The return-path correction is verified. Longer normal use is needed to establish
that the recurring stalls are resolved. On recurrence, preserve paired physical
client/LAN captures with timestamps and capture-drop counts before changing policy.
A rollback is to disable this specific rule and renew only the affected Home UDP
state; that restores the previous return-path behavior and may restore the fault.
Keep console access available for controlled testing. Do not reset all states.

Reference: [OPNsense firewall settings](https://docs.opnsense.org/manual/firewall_settings.html).
Raw captures, MAC addresses, endpoint addresses and private hostnames remain outside
this public record. Authentication fallback is a separate unresolved question.

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
