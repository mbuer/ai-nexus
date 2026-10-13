param(
    [Parameter(Mandatory=$true)][string]$CertificateBundle,
    [Parameter(Mandatory=$true)][string]$ReviewDirectory,
    [Parameter(Mandatory=$true)][string]$UtilityHost,
    [switch]$InstallApproved
)
$ErrorActionPreference = 'Stop'
if (-not $InstallApproved) {
    Write-Host 'Plan only. After explicit approval, add -InstallApproved to upload and install parallel HTTPS.'
    Write-Host 'This adds a LAN-only 443 nginx site and scoped firewall rule. No feedback, AI Nexus, SQL or Git change.'
    return
}
if ($UtilityHost -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+$') { throw 'Expected named-account SSH destination.' }
$journalReview = Get-Content -LiteralPath (Join-Path $ReviewDirectory 'install-review.json') -Raw | ConvertFrom-Json
$journalManifest = Get-Content -LiteralPath (Join-Path $CertificateBundle 'manifest.json') -Raw | ConvertFrom-Json
if ($journalManifest.export_status -ne 'complete' -or $journalManifest.address -ne $journalReview.address -or
    $journalManifest.authority_sha256 -ne $journalReview.authority_sha256) { throw 'Certificate identity differs from reviewed package.' }
$journalUpload = @()
foreach ($journalEntry in $journalReview.files_sha256.PSObject.Properties) {
    switch ($journalEntry.Name) {
        'journal-server.crt' { $journalFile = Join-Path $CertificateBundle 'utility\journal-server.crt' }
        'journal-server.key' { $journalFile = Join-Path $CertificateBundle 'utility\journal-server.key' }
        'journal-authority.crt' { $journalFile = Join-Path $CertificateBundle 'device-trust\journal-authority.crt' }
        'https_plan.py' { $journalFile = Join-Path $ReviewDirectory $journalEntry.Name }
        'install_https.py' { $journalFile = Join-Path $ReviewDirectory $journalEntry.Name }
        'nginx-https.conf.example' { $journalFile = Join-Path $ReviewDirectory $journalEntry.Name }
        default { throw 'Unexpected upload file. No transfer started.' }
    }
    if ((Get-FileHash -LiteralPath $journalFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $journalEntry.Value) {
        throw "Reviewed file changed: $($journalEntry.Name)"
    }
    $journalUpload += $journalFile
}
if ($journalUpload.Count -ne 6) { throw 'Incomplete reviewed package.' }
$journalUpload += Join-Path $ReviewDirectory 'install-review.json'
Write-Host 'Installing approved parallel HTTPS on Utility. Administration passwords remain interactive.'
Write-Host 'Only the server key/certificate and public authority certificate are uploaded; the signing key/backup stay here.'
$journalStage = ((& ssh $UtilityHost 'mktemp -d /tmp/journal-https.XXXXXXXXXX') -join '').Trim()
if ($LASTEXITCODE -ne 0 -or $journalStage -notmatch '^/tmp/journal-https\.[A-Za-z0-9]{10}$') { throw 'Private staging failed.' }
& scp @journalUpload "${UtilityHost}:$journalStage/"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed. No installation started; private staging retained.' }
# Do not pipe SSH output: nested sudo/authentication prompts must stay visible.
& ssh -t $UtilityHost "sudo env PYTHONDONTWRITEBYTECODE=1 python3 $journalStage/install_https.py --install-approved"
if ($LASTEXITCODE -ne 0) { throw 'Installation stopped. Paste output before retrying; staging/recovery files retained.' }
Write-Host 'Server checks passed. Open the HTTPS address on Windows and Android; confirm no certificate warning and test Stream Deck.'
Write-Host 'No feedback service enabled. Paste the output to record deployment.'
