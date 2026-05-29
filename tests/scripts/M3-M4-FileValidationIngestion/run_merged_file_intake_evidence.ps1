# M13 - Containerization Start
# Historical wrapper. Official M3/M4 evidence runs through Docker only.
# M13 End

[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\.." | Select-Object -ExpandProperty Path),
    [switch]$SkipBuild,
    [switch]$LeaveStackRunning
)

$ErrorActionPreference = "Stop"

$runner = Join-Path $ProjectRoot "tests\scripts\regression\run_docker_full_regression_evidence.ps1"
if (-not (Test-Path $runner)) {
    throw "Docker regression runner not found: $runner"
}

Write-Host "This historical M3/M4 script now delegates to the M13 container-first Docker regression runner."

$args = @("-ProjectRoot", $ProjectRoot)
if ($SkipBuild) { $args += "-SkipBuild" }
if ($LeaveStackRunning) { $args += "-LeaveStackRunning" }

& $runner @args
exit $LASTEXITCODE
