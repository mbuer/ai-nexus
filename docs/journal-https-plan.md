# Learning HTTPS with the Journal

Operator results confirm the approved private authority, device trust on Windows
and Android, and HTTPS installed on Utility. Reading works without certificate
warnings on both devices, and Companion still works. The authority signing key
and encrypted backup stay off Utility; only the server pair and public authority
were uploaded. Live addressing, fingerprints and receipts stay in private records.

This chapter explains the design and maintenance workflow. Leaf renewal tooling is
prepared and tested locally; live renewal and unattended renewal are not installed.
The issued leaf expires January 10, 2027; plan the first renewal around December 10,
2026. The authority expires October 11, 2028. Renewing under the same authority
does not require enrolling reader devices again.

## Where it belongs

Terminate journal HTTPS on Utility's existing nginx server. Keep the journal and
its narrow feedback route together; do not route them through AI Nexus or attach
Utility to the AI bridge. Ubuntu Infra does not need another workload for this
first setup. OPNsense, household routing/DHCP and Grafana remain unchanged.
Broader lab-wide certificate/proxy infrastructure is a separate later design.

The current HTTP reading site can remain available during verification. Do not
enable feedback writes there. Choose a free LAN-bound HTTPS listener only after
inspection. Test nginx syntax and keep the previous site configuration before
any reload. Existing Stream Deck/Companion listeners and firewall rules stay intact.

## Trust and identity

A certificate says which server identity a key belongs to. TLS encrypts the
connection and lets the browser verify that identity. Installing trust is different
from ignoring a browser warning: both client devices must recognize the issuer
and the address must match the certificate's subject alternative name.

The selected private-CA design separates signing authority from the web server. Keep its signing key offline on
the operator's protected workstation, outside Git and away from the web service.
Utility receives only its journal server certificate and server private key.
Windows and Android receive only the public CA certificate, with its fingerprint
checked before installation. Never transfer a CA private key to a client phone.
Trusting a private CA is a deliberate device trust decision; its signing authority
is broader than a single page, so it needs an agreed storage/recovery procedure.

For the first address, consider a certificate covering Utility's stable LAN IP.
This avoids adding a DNS dependency, but first verify that its address is stable
or reserved. A later local hostname requires a separately agreed resolution plan.
Do not assume mDNS, OPNsense DNS or a household DNS override is already available.

The certificate workflow must retain issuer/leaf fingerprints, expiry dates,
private recovery locations and a manual renewal procedure. Private addresses,
keys and device inventory remain outside public Git. Certificate generation,
trust-store installation and firewall changes each require operator approval.

## Verification and rollback

The prepared Windows certificate builder uses the optional pinned cryptography
package. It exports the authority signing key only as encrypted PKCS8, a public
authority certificate, and a separate server certificate/key. The authority has
no intermediate-CA permission; the leaf has an IP SAN and server-auth usage.
The issued lifetimes are two years and ninety days respectively. This means
the server certificate needs renewal before its ninety-day expiry; unattended
renewal is not configured. Do not issue the initial certificate without an agreed
renewal/reminder procedure. Authority replacement requires device trust enrollment
again and is a separate deliberate action.

The builder now supports `verify_material`, `renew`, `authority_backup`,
`restore_authority` and `recover_material`. Verification checks hashes, fingerprints,
certificate/key pairs, source address, server-auth usage and recorded expiry.
Renewal rotates the leaf key while preserving the original encrypted signer and
public authority identity. An expired leaf can be renewed if the issuer remains
valid; an issuer with fewer than ninety days remaining requires replacement review.
No function silently creates a new trust anchor during renewal.

The portable authority backup contains only the encrypted PKCS8 signing key and
public authority certificates. The password is stored separately in the operator's
password manager. Keep its recorded SHA-256 authority fingerprint separately too;
restoration requires that expected identity rather than trusting a fingerprint
supplied by the backup alone. JSON field/file checks and hashes detect corruption,
but they are not a digital signature or proof that an arbitrary archive is trusted.
Recovery verifies the original issuer and prepares a fresh server certificate/key.
It does not need to preserve the old plaintext server key in the authority backup.

Disposable in-memory tests verify signatures, encryption, SAN/usage, expiry,
renewal identity preservation, wrong passwords, backup tampering and recovery.
They create no real trust anchor and do not verify actual device trust. A protected
Windows output-folder/export CLI is now prepared; its actual ACL integration and
the device/Utility installation plan still need verification and approval before
production material is created.

`clients/windows/journal/Prepare-Journal-Https.ps1` defaults to a plan. Only its
explicit creation switch provisions a new private output folder, removes inherited
access, grants the current user inheritable access and invokes the local builder.
The Python exporter independently checks owner, protected ACL, explicit user-only
access and absence of reparse points before asking for the password-manager
passphrase. Do not use an elevated administrator console for preparation.

Exports separate `authority/`, `utility/` and `device-trust/`. Only `utility/`
contains the two files to upload to the web server; only `device-trust/` contains
public trust certificates. Copy the encrypted authority backup to a separate safe
location and verify restoration with the recorded fingerprint before deployment.
The prepared exporter performs a memory restoration check, but cannot establish
that the operator has actually copied and retained the separate backup.

Output is never overwritten. An incomplete manifest is written before export;
exact exported bytes are reloaded and checked before the manifest becomes complete.
Interrupted exports remain for inspection, never silently retried or deleted.
Renewal uses a complete prior export and writes a new directory, retaining the
earlier keys and certificates. The script installs no trust, opens no network
connection, changes no firewall and restarts no service.

Before feedback activation, verify the actual Windows browser and Android browser
can open the HTTPS journal without certificate warnings. Confirm the certificate
matches the address, the HTTPS listener is restricted to the intended LAN, and
the original HTTP journal and Stream Deck still work. Do not disable verification.

The later feedback login should use HTTPS and a separate personal credential,
mapped to one reviewer UUID across devices. Its setup remains undecided. A browser
login is not a reason to reuse an SSH key or administration password.

Rollback retains the HTTP reading site and prior nginx configuration. Stop the
feedback route before reverting secure access; preserve queued reviews. Remove
the deliberately installed trust anchor from devices only as an explicit operator
step, using the recorded fingerprint rather than deleting unrelated certificates.

References: [nginx HTTPS](https://nginx.org/en/docs/http/ngx_http_ssl_module.html),
[Windows certificate tools](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/certutil),
[Android certificate guidance](https://support.google.com/pixelphone/answer/2844832?hl=en).
Android menu names and browser behavior must be checked on the actual phone.

## Initial installation candidate

The reviewed installer adds a separate nginx site on the reserved Utility address
and TCP/443. It preserves the HTTP site and creates no feedback route. The Windows
launcher defaults to a plan; installation requires its explicit approval switch.
It checks exact upload hashes, sends only the server pair plus the public authority
certificate and installer sources, and keeps SSH output direct for password prompts.
The authority signing key and encrypted backup never leave Windows.

The public authority is included only to verify the server chain, address and
purpose. Uploads use a private temporary directory. Before installation the host
checks interface addressing, unused port, active UFW, absence of preexisting HTTPS
files/rules, nginx syntax, certificate lifetime/key pair and existing services.
The root-owned server key has mode 0600 in a 0700 directory. HTTPS remains LAN
restricted in both nginx and one exact UFW rule; no DNS, OPNsense or AI changes.

Recovery stores a copy and hash of the HTTP configuration and an installation
receipt. Failures remove only the owned HTTPS link and attempted firewall rule;
the source files, certificates and receipt remain for inspection. A changed link
is never removed automatically. Rollback errors are recorded, not treated as
success. Do not rerun after interruption or failure: inspect the receipt first.
Renewal is deliberately a separate procedure; the initial installer refuses
existing material. Renew before the server certificate expires using the same CA.

Offline checks cover exclusive writes, early staging rejection and ownership-
limited rollback. Windows parsing and package hashes are checked separately.
Actual Ubuntu nginx/OpenSSL behavior, firewall enforcement and device trust remain
deployment checks. A TCP connection to Companion confirms reachability, not Stream
Deck functionality; the operator must also test the device. No installation or
device-trust success should be inferred from preparation alone.

## Server certificate renewal

Renew about every 60 days, before the 90-day server certificate expires. Keep the
same authority and reserved address. Device trust then stays valid without another
installation. Keep the most recent complete private export for the next renewal.
The encrypted authority backup remains the separate recovery option.

After explicit approval for local certificate creation, run
`Prepare-Journal-Https.ps1 -RenewFrom PREVIOUS_PRIVATE_EXPORT -CreateApproved`.
Enter the authority passphrase interactively. This writes a fresh protected
export, checks the encrypted authority and rotates only the server pair.

Server replacement requires separate deployment approval. The prepared
`Renew-Journal-Https.ps1 -PreviousBundle PREVIOUS_PRIVATE_EXPORT
-ReplacementBundle NEW_PRIVATE_EXPORT -UtilityHost UTILITY_SSH_DESTINATION`
defaults to a plan. Add `-RenewApproved` only after approval. It verifies matching
authority/address, a newer expiry and unchanged exported bytes. It uploads only
the server pair, public authority and bounded installer package.

The host refuses a different live certificate or an unfinished prior renewal.
It verifies the old and replacement chain/address/key, preserves root-only
recovery copies, replaces the pair, checks nginx syntax, reloads and verifies
the actual served certificate fingerprint. HTTP and configuration hashes are
checked too. Neither firewall nor nginx configuration nor device trust changes.
An expired old leaf may be replaced, but the replacement and its authority must
be valid. Failed checks attempt to restore both old files and reload them; an
expired old leaf cannot restore trusted browsing. Recovery failures are explicit.

Do not retry after interruption. Inspect the retained renewal receipt and pending
files first; pair replacement is not atomic across two files, and a process crash
can leave a partial pair on disk while nginx retains its loaded certificate.
Each confirmed successful renewal retains its backup and receipt. The next renewal
must name the new export, not the original one. Offline tests verify both-file
restoration, successful checking, recovery failure reporting and refusal to
overwrite interrupted staging. Live Ubuntu renewal has not yet been exercised.
