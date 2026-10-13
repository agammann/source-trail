param(
    [string]$PythonPath,
    [ValidateRange(1, 65535)]
    [int]$Port = 8765,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$sourceTrailCandidates = @()

if ($PythonPath) {
    $sourceTrailCandidates += @{ Executable = $PythonPath; Prefix = @() }
} elseif ($env:SOURCETRAIL_PYTHON) {
    $sourceTrailCandidates += @{ Executable = $env:SOURCETRAIL_PYTHON; Prefix = @() }
} else {
    $sourceTrailVenv = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $sourceTrailVenv) {
        $sourceTrailCandidates += @{ Executable = $sourceTrailVenv; Prefix = @() }
    }
    foreach ($sourceTrailCommand in @('py', 'python', 'python3')) {
        $sourceTrailResolved = Get-Command $sourceTrailCommand -CommandType Application -ErrorAction SilentlyContinue
        if (-not $sourceTrailResolved) { continue }
        $sourceTrailDiscovered = @{
            Executable = $sourceTrailResolved.Source
            Prefix = @()
        }
        if ($sourceTrailCommand -eq 'py') { $sourceTrailDiscovered.Prefix = @('-3') }
        $sourceTrailCandidates += $sourceTrailDiscovered
    }
}

$sourceTrailPython = $null
$sourceTrailPrefix = @()
$sourceTrailVersion = $null
foreach ($sourceTrailCandidate in $sourceTrailCandidates) {
    try {
        if (Test-Path -LiteralPath $sourceTrailCandidate.Executable -PathType Leaf) {
            $sourceTrailExecutable = (Resolve-Path -LiteralPath $sourceTrailCandidate.Executable).ProviderPath
        } else {
            $sourceTrailExecutable = (Get-Command $sourceTrailCandidate.Executable -CommandType Application -ErrorAction Stop).Source
        }
        $sourceTrailProbePrefix = @($sourceTrailCandidate.Prefix)
        $sourceTrailProbe = & $sourceTrailExecutable @sourceTrailProbePrefix -c "import sys; print(sys.version.split()[0]); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $sourceTrailPython = $sourceTrailExecutable
            $sourceTrailPrefix = $sourceTrailProbePrefix
            $sourceTrailVersion = $sourceTrailProbe
            break
        }
    } catch {
        continue
    }
}
if (-not $sourceTrailPython) {
    throw 'A working Python 3.11 or later is required. Install Python, create .venv, or pass -PythonPath with the interpreter executable path.'
}

Write-Output "Using Python $sourceTrailVersion"
if ($Check) { return }

Push-Location $PSScriptRoot
try {
    Write-Output "Open http://127.0.0.1:$Port after the server starts. Press Ctrl+C to stop."
    & $sourceTrailPython @sourceTrailPrefix -m sourcetrail serve --host 127.0.0.1 --port $Port
    $sourceTrailExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $sourceTrailExitCode
