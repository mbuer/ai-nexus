[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CertificatePath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [switch]$InstallApproved,
    [switch]$RemoveApproved
)
$ErrorActionPreference = 'Stop'
if ($InstallApproved -and $RemoveApproved) { throw 'Choose installation or removal, not both.' }
$journalCertificateFile = Get-Item -LiteralPath $CertificatePath -Force
if ($journalCertificateFile.PSIsContainer -or ($journalCertificateFile.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $journalCertificateFile.Length -gt 20000) {
    throw 'Unexpected public certificate file.'
}
$journalCertificate = [Security.Cryptography.X509Certificates.X509Certificate2]::new($journalCertificateFile.FullName)
try {
    if ($journalCertificate.HasPrivateKey) { throw 'Device trust must use a public certificate only.' }
    $journalHasher = [Security.Cryptography.SHA256]::Create()
    try { $journalFingerprint = [BitConverter]::ToString($journalHasher.ComputeHash($journalCertificate.RawData)).Replace('-', '').ToLowerInvariant() }
    finally { $journalHasher.Dispose() }
    if ($journalFingerprint -ne $ExpectedSha256.ToLowerInvariant()) { throw 'Certificate differs from the recorded authority fingerprint. Nothing changed.' }
    $journalConstraint = @($journalCertificate.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.19' })
    if ($journalConstraint.Count -ne 1 -or -not $journalConstraint[0].CertificateAuthority -or -not $journalConstraint[0].Critical) { throw 'Expected the reviewed public authority certificate.' }
    if ($journalCertificate.Subject -ne $journalCertificate.Issuer) { throw 'Expected the self-issued journal authority.' }
    if ($journalCertificate.NotBefore -gt (Get-Date) -or $journalCertificate.NotAfter -le (Get-Date)) { throw 'Authority is outside its validity period.' }
    Write-Host ('Authority: ' + $journalCertificate.Subject)
    Write-Host ('SHA-256: ' + $journalFingerprint)
    Write-Host ('Expires: ' + $journalCertificate.NotAfter.ToUniversalTime().ToString('o'))
    Write-Host 'Target: Trusted Root Certification Authorities for this Windows user only.'
    $journalStore = [Security.Cryptography.X509Certificates.X509Store]::new('Root', 'CurrentUser')
    try {
        $journalMode = if ($InstallApproved -or $RemoveApproved) { 'ReadWrite' } else { 'ReadOnly' }
        $journalStore.Open([Security.Cryptography.X509Certificates.OpenFlags]::$journalMode)
        $journalPresent = @($journalStore.Certificates | Where-Object { $_.Thumbprint -eq $journalCertificate.Thumbprint })
        if ($InstallApproved) {
            if ($journalPresent.Count -eq 0) { $journalStore.Add($journalCertificate) }
            Write-Host 'Reviewed authority installed for the current Windows user. No machine-wide trust changed.'
        } elseif ($RemoveApproved) {
            foreach ($journalEntry in $journalPresent) { $journalStore.Remove($journalEntry) }
            Write-Host 'Only the matching journal authority removed from current-user trust.'
        } else {
            Write-Host ('Already present: ' + ($journalPresent.Count -gt 0))
            Write-Host 'Plan only. No certificate trust was added or removed.'
        }
    } finally { $journalStore.Close() }
} finally { $journalCertificate.Dispose() }
