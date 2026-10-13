[CmdletBinding()]
param(
    [string]$UtilityAddress,
    [string]$RenewFrom,
    [string]$PythonExe,
    [switch]$CreateApproved
)
$ErrorActionPreference = 'Stop'
if ([bool]$UtilityAddress -eq [bool]$RenewFrom) { throw 'Specify UtilityAddress for initial preparation or RenewFrom for renewal.' }
if (-not $PythonExe) { $PythonExe = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Specify a Python executable with requirements-tls.txt installed.' }
$journalOutput = Join-Path $PSScriptRoot ('private\tls-' + [Guid]::NewGuid().ToString('N'))
Write-Host 'Local certificate preparation only. No trust installation, upload or service change.'
Write-Host ('Private output: ' + $journalOutput)
if (-not $CreateApproved) {
    Write-Host 'Plan only. After approval, add -CreateApproved to create encrypted authority and server material.'
    return
}
if (Test-Path -LiteralPath $journalOutput) { throw 'Output already exists; nothing overwritten.' }
New-Item -ItemType Directory -Path $journalOutput > $null
$journalSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
# Replace inherited access on this new directory before any key is generated.
& icacls.exe $journalOutput /inheritance:r /grant:r ('*' + $journalSid + ':(OI)(CI)F') > $null
if ($LASTEXITCODE -ne 0) { throw 'Private directory ACL setup failed; no certificate generation started.' }
$journalArguments = @('-B', (Join-Path $PSScriptRoot 'certificate_export.py'), '--output', $journalOutput)
if ($UtilityAddress) { $journalArguments += @('--new-address', $UtilityAddress) }
else { $journalArguments += @('--renew-from', $RenewFrom) }
& $PythonExe @journalArguments
if ($LASTEXITCODE -ne 0) { throw 'Preparation stopped. Retain the private output directory and inspect before retrying.' }
Write-Host ('Completed private material: ' + $journalOutput)
