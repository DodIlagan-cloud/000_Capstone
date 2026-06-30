# M13 - Containerization Start
# Runs consolidated module unit tests inside the M13 Stats runtime container.
# Each module runs in a separate pytest process because service modules share the top-level Python package name "app".
# Static contract checks expect the equivalent command forms: docker exec stats-runtime and docker cp.

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$TestInputDir = "tests/input",
    [string]$EvidenceDir = "tests\results\M13-ContainerFirstTesting",
    [string]$ComposeFile = "infrastructure\compose\stats-runtime.compose.yml",
    [string]$EnvFile = "infrastructure\compose\.env.container",
    [string]$ContainerRoot = "/app",
    [switch]$LeaveStackRunning
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

$composePath = Join-Path $RepoRoot $ComposeFile
$envPath = Join-Path $RepoRoot $EnvFile
$evidencePath = Join-Path $RepoRoot $EvidenceDir
if (-not (Test-Path $composePath)) {
    throw "Compose file not found: $composePath"
}
if (-not (Test-Path $envPath)) {
    throw "Container env file not found: $envPath"
}
$testInputPath = Join-Path $RepoRoot $TestInputDir
# Default container fixture path remains /app/tests/input; override ContainerRoot only when the runtime root changes.
$containerInputDir = "$ContainerRoot/tests/input"

$runId = Get-Date -Format "yyyyMMddHHmmss"
$date = Get-Date -Format "yyyy-MM-dd"
New-Item -ItemType Directory -Force -Path $evidencePath | Out-Null
$rawOutputPath = Join-Path $evidencePath "M13-container-first-module-unit-raw-output-$date.txt"
$summaryPath = Join-Path $evidencePath "M13-container-first-module-unit-summary-$date.md"

Set-Content -Path $rawOutputPath -Value @(
    "M13 container-first module unit tests",
    "Date: $date",
    "Command: powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1",
    "LeaveStackRunning: $LeaveStackRunning",
    ""
) -Encoding UTF8

function Write-EvidenceLine {
    param([string]$Message)
    Write-Host $Message
    Add-Content -Path $rawOutputPath -Value $Message -Encoding UTF8
}

function Invoke-LoggedNative {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $FilePath @Arguments 2>&1 | ForEach-Object {
        $line = $_.ToString()
        Write-Host $line
        Add-Content -Path $rawOutputPath -Value $line -Encoding UTF8
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    return $exitCode
}

$testSuites = @(
    # M0 Foundation Start
    @{ Name = "M0 Architecture Foundation"; Path = "tests\scripts\M0-ArchitectureFoundation\M0-ArchitectureFoundation_terminal_check.py"; Temp = "m0-architecture-foundation" },
    # M0 Foundation End
    @{ Name = "M1 Identity Access"; Path = "tests\unit\identity_access_module"; Temp = "identity-access" },
    @{ Name = "M3/M4 File Validation and Ingestion"; Path = "tests\unit\file_validation_module"; Temp = "file-validation" },
    @{ Name = "M5 Document Parsing"; Path = "tests\unit\document_parsing_module"; Temp = "document-parsing" },
    # M7 - Transaction Extraction Start
    @{ Name = "M7 Transaction Extraction"; Path = "tests\unit\transaction_extraction_module"; Temp = "transaction-extraction" },
    # M7 End
    # M8 - Data Validation Module Start
    @{ Name = "M8 Data Validation"; Path = "tests\unit\data_validation_module"; Temp = "data-validation" },
    # M8 End
    # M12 - Email Ingestion Module Start
    @{ Name = "M12 Email Ingestion"; Path = "tests\unit\email_ingestion_module"; Temp = "email-ingestion" },
    # M12 End
    # M13 - Containerization Start
    @{ Name = "M2 Stats Web Container Config"; Path = "tests\integration\test_stats_web_orchestration_config.py"; Temp = "m2-stats-web-config" },
    @{ Name = "M13 Container Contract"; Path = "tests\integration\test_m13_containerization_contract.py"; Temp = "m13-container-contract" }
    # M13 End
)

Push-Location $RepoRoot
try {
    Write-EvidenceLine "=== Docker Compose Build/Start ==="
    $composeExit = Invoke-LoggedNative "docker" @("compose", "--file", $ComposeFile, "--env-file", $EnvFile, "up", "--build", "--detach")
    if ($composeExit -ne 0) {
        throw "Docker compose startup failed."
    }
}
finally {
    Pop-Location
}

if (Test-Path $testInputPath) {
    Write-EvidenceLine "=== Copy tests/input into stats-runtime ==="
    $mkdirExit = Invoke-LoggedNative "docker" @("exec", "stats-runtime", "sh", "-lc", "mkdir -p $containerInputDir")
    $copyExit = Invoke-LoggedNative "docker" @("cp", "$testInputPath\.", "stats-runtime:$containerInputDir/")
    if ($mkdirExit -ne 0 -or $copyExit -ne 0) {
        throw "Copying tests/input into stats-runtime failed."
    }
}

$failed = 0
foreach ($suite in $testSuites) {
    Write-EvidenceLine ""
    Write-EvidenceLine "=== $($suite.Name) ==="
    $suitePath = Join-Path $RepoRoot $suite.Path
    if (-not (Test-Path $suitePath)) {
        Write-EvidenceLine "Skipping missing suite folder: $($suite.Path)"
        continue
    }

    $containerSuitePath = "$ContainerRoot/" + ($suite.Path -replace "\\", "/")
    $suiteTemp = "/tmp/stats-pytest/$($suite.Temp)-$runId"
    $command = "mkdir -p /tmp/stats-pytest && cd $ContainerRoot && export STATS_APP_ROOT=$ContainerRoot && export STATS_TESTDATA_DIR=$containerInputDir && export STATS_PARSING_TESTDATA_DIR=$containerInputDir && /opt/stats/runtime/bin/pytest $containerSuitePath --basetemp $suiteTemp"
    $suiteExit = Invoke-LoggedNative "docker" @("exec", "stats-runtime", "sh", "-lc", $command)
    if ($suiteExit -ne 0) {
        $failed += 1
    }
}

if ($failed -gt 0) {
    throw "$failed consolidated module unit test suite(s) failed."
}

Write-EvidenceLine ""
Write-EvidenceLine "Result: PASSED"

@(
    "# M13 Container-First Module Unit Tests",
    "",
    "Date: $date",
    "",
    "Command:",
    "",
    "    powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1",
    "",
    "Result: **PASSED**",
    "",
    "Evidence:",
    "",
    "- Raw output: M13-container-first-module-unit-raw-output-$date.txt",
    "",
    "Execution boundary:",
    "",
    "- Docker Compose starts the Stats runtime.",
    "- Approved tests/input fixtures are copied into stats-runtime.",
    "- Module tests run inside the stats-runtime container through /opt/stats/runtime/bin/pytest.",
    "- Covered suites: M0, M1, M2 config, M3/M4, M5, M7, M8, and M13 container contract checks.",
    ""
) | Set-Content -Path $summaryPath -Encoding UTF8

if (-not $LeaveStackRunning) {
    Write-EvidenceLine ""
    Write-EvidenceLine "=== Docker Compose Cleanup ==="
    Push-Location $RepoRoot
    try {
        $cleanupExit = Invoke-LoggedNative "docker" @("compose", "--file", $ComposeFile, "--env-file", $EnvFile, "down")
        if ($cleanupExit -ne 0) {
            throw "Docker compose cleanup failed."
        }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-EvidenceLine ""
    Write-EvidenceLine "Docker Compose cleanup skipped because -LeaveStackRunning was supplied."
}
# M13 End
