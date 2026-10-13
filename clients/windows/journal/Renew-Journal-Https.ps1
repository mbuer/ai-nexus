param(
    [Parameter(Mandatory=$true)][string]$PreviousBundle,
    [Parameter(Mandatory=$true)][string]$ReplacementBundle,
    [Parameter(Mandatory=$true)][string]$UtilityHost,
    [switch]$RenewApproved
)
$ErrorActionPreference = 'Stop'
if (-not $RenewApproved) {
    Write-Host 'Plan only: replace Utility server certificate/key using the same authority, retaining recovery copies.'
    Write-Host 'Prepare replacement locally first. Deployment requires separate approval and -RenewApproved.'
    return
}
if ($UtilityHost -notmatch '^[A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+$') { throw 'Expected named-account SSH destination.' }
$journalPrevious = Get-Content -LiteralPath (Join-Path $PreviousBundle 'manifest.json') -Raw | ConvertFrom-Json
$journalReplacement = Get-Content -LiteralPath (Join-Path $ReplacementBundle 'manifest.json') -Raw | ConvertFrom-Json
if ($journalPrevious.export_status -ne 'complete' -or $journalReplacement.export_status -ne 'complete' -or
    $journalPrevious.address -ne $journalReplacement.address -or
    $journalPrevious.authority_sha256 -ne $journalReplacement.authority_sha256 -or
    $journalPrevious.server_sha256 -eq $journalReplacement.server_sha256 -or
    [DateTimeOffset]$journalReplacement.server_expires -le [DateTimeOffset]$journalPrevious.server_expires) {
    throw 'Expected complete exports with the same authority/address and a newer server certificate.'
}
$journalOldCertificate = Join-Path $PreviousBundle 'utility\journal-server.crt'
if ((Get-FileHash -LiteralPath $journalOldCertificate).Hash.ToLowerInvariant() -ne $journalPrevious.files_sha256.'journal-server.crt') {
    throw 'Previous certificate export changed.'
}
$journalPackage = Join-Path $PSScriptRoot ('private\renewal-review-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $journalPackage | Out-Null
$journalSources = [ordered]@{}
$journalHostSources = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\deploy\journal-host'))
foreach ($journalName in @('renew_https.py','install_https.py','https_plan.py')) {
    Copy-Item -LiteralPath (Join-Path $journalHostSources $journalName) -Destination (Join-Path $journalPackage $journalName)
    $journalSources[$journalName] = Join-Path $journalPackage $journalName
}
$journalSources['journal-authority.crt'] = Join-Path $ReplacementBundle 'device-trust\journal-authority.crt'
$journalSources['journal-server.crt'] = Join-Path $ReplacementBundle 'utility\journal-server.crt'
$journalSources['journal-server.key'] = Join-Path $ReplacementBundle 'utility\journal-server.key'
$journalHashes = [ordered]@{}
foreach ($journalName in $journalSources.Keys) {
    $journalHashes[$journalName] = (Get-FileHash -LiteralPath $journalSources[$journalName]).Hash.ToLowerInvariant()
    if ($journalReplacement.files_sha256.PSObject.Properties.Name -contains $journalName) {
        if ($journalHashes[$journalName] -ne $journalReplacement.files_sha256.$journalName) { throw 'Replacement export changed.' }
    }
}
$journalReview = [ordered]@{
    schema_version='journal-https-renewal-v1'; address=$journalReplacement.address;
    authority_sha256=$journalReplacement.authority_sha256; server_sha256=$journalReplacement.server_sha256;
    server_expires=$journalReplacement.server_expires;
    previous_certificate_file_sha256=$journalPrevious.files_sha256.'journal-server.crt'; files_sha256=$journalHashes
}
$journalReviewPath = Join-Path $journalPackage 'renewal-review.json'
$journalReview | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $journalReviewPath -Encoding UTF8
Write-Host 'Approved server renewal only. Certificate authority private key/backup stay on Windows.'
$journalStage = ((& ssh $UtilityHost 'mktemp -d /tmp/journal-renewal.XXXXXXXXXX') -join '').Trim()
if ($LASTEXITCODE -ne 0 -or $journalStage -notmatch '^/tmp/journal-renewal\.[A-Za-z0-9]{10}$') { throw 'Private staging failed.' }
$journalUpload = @($journalSources.Values) + @($journalReviewPath)
& scp @journalUpload "${UtilityHost}:$journalStage/"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed; no server replacement started.' }
& ssh -t $UtilityHost "sudo env PYTHONDONTWRITEBYTECODE=1 python3 $journalStage/renew_https.py --renew-approved"
if ($LASTEXITCODE -ne 0) { throw 'Renewal stopped. Paste output; do not retry before inspecting recovery.' }
Write-Host 'Keep the new export for the next renewal. Check HTTPS on Windows and Android. No trust reinstallation needed.'
