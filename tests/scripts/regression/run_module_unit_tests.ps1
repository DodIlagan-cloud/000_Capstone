# M13 - Containerization Start
# Runs consolidated host-side module unit tests from root tests/unit/<module>/ folders.
# Each module runs in a separate pytest process because service modules share the top-level Python package name "app".

[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$TestInputDir = "tests/input"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
}

$testInputPath = Join-Path $RepoRoot $TestInputDir
if (Test-Path $testInputPath) {
    $env:STATS_TESTDATA_DIR = (Resolve-Path $testInputPath).Path
    $env:STATS_PARSING_TESTDATA_DIR = (Resolve-Path $testInputPath).Path
}

$tempRoot = Join-Path $RepoRoot "tests\\results\\pytest-tmp"
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
$runId = Get-Date -Format "yyyyMMddHHmmss"

$testSuites = @(
    @{ Name = "M1 Identity Access"; Path = "tests\unit\identity_access_module"; Temp = "identity-access" },
    @{ Name = "M3/M4 File Validation and Ingestion"; Path = "tests\unit\file_validation_module"; Temp = "file-validation" },
    @{ Name = "M5 Document Parsing"; Path = "tests\unit\document_parsing_module"; Temp = "document-parsing" }
)

$failed = 0
foreach ($suite in $testSuites) {
    Write-Host ""
    Write-Host "=== $($suite.Name) ==="
    $suitePath = Join-Path $RepoRoot $suite.Path
    if (-not (Test-Path $suitePath)) {
        Write-Host "Skipping missing suite folder: $($suite.Path)"
        continue
    }

    $suiteTemp = Join-Path $tempRoot "$($suite.Temp)-$runId"
    pytest $suitePath --basetemp $suiteTemp
    if ($LASTEXITCODE -ne 0) {
        $failed += 1
    }
}

if ($failed -gt 0) {
    throw "$failed consolidated module unit test suite(s) failed."
}

Write-Host ""
Write-Host "Result: PASSED"
# M13 End
