[CmdletBinding()]
param(
    [ValidateRange(1, 2147483647)][int]$AnalysisId = 9,
    [ValidatePattern('^[A-Za-z0-9_.@:-]+$')][string]$AiHost = 'AI_HOST',
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_.@:-]+$')][string]$UtilityHost,
    [string]$JournalUrl,
    [string]$PythonExe,
    [string]$Headline,
    [switch]$ReadOnly
)

$ErrorActionPreference = 'Stop'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = $utf8

foreach ($name in @('ssh', 'scp')) {
    if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Windows OpenSSH command '$name' is unavailable."
    }
}
if (-not $PythonExe) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $PythonExe = $bundledPython }
    else { throw 'Specify -PythonExe with a Python 3 executable.' }
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Python executable not found.' }

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$renderer = Join-Path $repoRoot 'services/birdynator/journal.py'
$publisher = Join-Path $repoRoot 'deploy/journal-host/publish_utility.py'
$privateDir = Join-Path $PSScriptRoot 'private'
$journalDir = Join-Path $privateDir 'journal'
New-Item -ItemType Directory -Force -Path $journalDir | Out-Null
$recordPath = Join-Path $privateDir "analysis-$AnalysisId.json"
$manifestPath = Join-Path $privateDir 'manifest.json'

Write-Host "Reading saved analysis $AnalysisId through your existing SSH connection..."
# This script queries one row in a read-only transaction. It does not run a model,
# change the container, export credentials, or invoke remote Git operations.
$reader = @'
import json
import birdynator
with birdynator.connect() as connection:
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SELECT id, model, source_latest_hour, source_digest, parameters, result_text FROM analysis_runs WHERE id = %s", (__ANALYSIS_ID__,))
        records = birdynator.rows_as_dicts(cursor)
if not records:
    raise SystemExit("Saved analysis not found")
print(json.dumps(records[0], default=str, ensure_ascii=True))
'@
$reader = $reader.Replace('__ANALYSIS_ID__', $AnalysisId.ToString())
$recordLines = $reader | & ssh $AiHost 'podman exec -i agent-birdynator python -'
if ($LASTEXITCODE -ne 0) { throw 'AI Nexus read failed. Connect WireGuard and check your SSH access.' }
$recordJson = $recordLines -join "`n"
$record = $recordJson | ConvertFrom-Json
if ([int]$record.id -ne $AnalysisId -or -not $record.result_text) { throw 'Unexpected saved analysis response.' }
[System.IO.File]::WriteAllText($recordPath, $recordJson, $utf8)
if ($ReadOnly) {
    Write-Host "Saved a private local copy: $recordPath"
    $evidence = $record.parameters.journal_report.evidence
    if ($evidence) {
        [ordered]@{
            analysis_id = $record.id
            cutoff = $record.source_latest_hour
            coverage = $evidence.coverage
            signals = $evidence.interesting_signals
            recent_comparable_days = @($evidence.daily_evidence | Select-Object -Last 7)
        } | ConvertTo-Json -Depth 20 | Write-Output
    } else { Write-Host 'This saved analysis has no evidence snapshot.' }
    return
}

Write-Host 'Rendering the saved report locally. Charts require matching saved evidence.'
$renderArgs = @('-B', $renderer, $recordPath, '--output', $journalDir)
if ($Headline) { $renderArgs += @('--headline', $Headline) }
& $PythonExe @renderArgs
if ($LASTEXITCODE -ne 0) { throw 'Local journal rendering failed; nothing uploaded.' }
& $PythonExe -B (Join-Path $PSScriptRoot 'prepare_upload.py') $journalDir $manifestPath
if ($LASTEXITCODE -ne 0) { throw 'Upload manifest validation failed.' }

Write-Host 'Creating a private staging directory on Utility...'
$stageLines = & ssh $UtilityHost 'mktemp -d /tmp/birdynator-upload.XXXXXXXXXX'
if ($LASTEXITCODE -ne 0) { throw 'Utility staging failed.' }
$stage = ($stageLines -join '').Trim()
if ($stage -notmatch '^/tmp/birdynator-upload\.[A-Za-z0-9]{10}$') { throw 'Unexpected remote staging path.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
$uploadFiles = @($manifest.files | ForEach-Object { Join-Path $journalDir $_.name })
$uploadFiles += @($manifestPath, $publisher)
& scp @uploadFiles "${UtilityHost}:$stage/"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed; the current Utility journal remains unchanged.' }

Write-Host 'Publishing on Utility. Enter its sudo password if requested.'
& ssh -t $UtilityHost "sudo python3 $stage/publish_utility.py $stage"
if ($LASTEXITCODE -ne 0) { throw 'Utility publication failed. See the error above; previous releases are retained.' }

Write-Host 'Published. Refresh your configured Journal address.'
if ($JournalUrl) { Write-Host $JournalUrl }
Write-Host "Private local records and journal archive: $privateDir"
