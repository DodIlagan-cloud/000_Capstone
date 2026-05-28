$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$configPath = Join-Path $repoRoot "tests\scripts\config\test-script-settings.json"
$localConfigPath = Join-Path $repoRoot "tests\scripts\config\test-script-settings.local.json"
$settings = Get-Content -Path $configPath -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $localConfigPath) {
    $localSettings = Get-Content -Path $localConfigPath -Raw | ConvertFrom-Json
    foreach ($section in @("evidenceFolders", "localPaths")) {
        if ($localSettings.PSObject.Properties.Name -contains $section) {
            foreach ($property in $localSettings.$section.PSObject.Properties) {
                $settings.$section | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value -Force
            }
        }
    }
}
function Resolve-ConfiguredPath {
    param([string] $PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $repoRoot $PathValue
}

$date = "2026-05-26"
$evidenceDir = Resolve-ConfiguredPath $settings.evidenceFolders.CrossModuleRegressionM3M4
$testDataDir = if ($env:STATS_TESTDATA_DIR) { $env:STATS_TESTDATA_DIR } else { $settings.localPaths.testDataDir }
if (-not $testDataDir) {
    throw "Set STATS_TESTDATA_DIR or tests\scripts\config\test-script-settings.local.json localPaths.testDataDir before running this evidence script."
}
$env:STATS_TESTDATA_DIR = $testDataDir

New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

$m1PytestOutput = Join-Path $evidenceDir "regression-m1-identity-pytest-raw-output-$date.txt"
$m2PytestOutput = Join-Path $evidenceDir "regression-m2-orchestration-pytest-raw-output-$date.txt"
$m3m4PytestOutput = Join-Path $evidenceDir "regression-m3m4-file-intake-pytest-raw-output-$date.txt"
$statsWebBuildOutput = Join-Path $evidenceDir "regression-stats-web-build-raw-output-$date.txt"
$summaryOutput = Join-Path $evidenceDir "regression-run-summary-$date.txt"
$completionMarker = Join-Path $evidenceDir "regression-run-complete.marker"

Remove-Item -Force -LiteralPath $completionMarker -ErrorAction SilentlyContinue

function Invoke-Step {
    param(
        [string] $Name,
        [string] $Command,
        [string] $OutputFile
    )

    Write-Host ""
    Write-Host "=== $Name ==="
    Write-Host "Command: $Command"

    Push-Location $repoRoot
    try {
        powershell.exe -NoProfile -ExecutionPolicy Bypass -Command $Command 2>&1 |
            Tee-Object -FilePath $OutputFile

        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

try {
    "Regression evidence run - $date" | Set-Content -Path $summaryOutput
    "Repository: $repoRoot" | Add-Content -Path $summaryOutput
    "STATS_TESTDATA_DIR: $testDataDir" | Add-Content -Path $summaryOutput
    "Coverage: M1 identity, M2 Stats Web orchestration, merged M3/M4 file intake with real PDFs, Stats Web build" |
        Add-Content -Path $summaryOutput

    Write-Host "Stats regression evidence run"
    Write-Host "Repository: $repoRoot"
    Write-Host "STATS_TESTDATA_DIR: $testDataDir"
    Write-Host "Each automated check is run once. Python modules run in separate pytest processes to avoid top-level app package import collisions."

    Invoke-Step `
        -Name "M1 identity module tests" `
        -Command "pytest modules\identity-access-module -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-m1" `
        -OutputFile $m1PytestOutput

    Invoke-Step `
        -Name "Merged M3/M4 file intake module tests" `
        -Command "pytest modules\file-validation-module\tests -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-m3m4" `
        -OutputFile $m3m4PytestOutput

    Invoke-Step `
        -Name "M2 orchestration integration test" `
        -Command "pytest tests\integration\test_stats_web_orchestration_config.py -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-m2" `
        -OutputFile $m2PytestOutput

    Invoke-Step `
        -Name "Stats Web build regression" `
        -Command "dotnet build apps\stats-web\stats.Web.csproj -o $evidenceDir\stats-web-build" `
        -OutputFile $statsWebBuildOutput

    "Result: PASSED" | Add-Content -Path $summaryOutput
    "Result: PASSED" | Set-Content -Path $completionMarker
    Write-Host ""
    Write-Host "Result: PASSED"
}
catch {
    "Result: FAILED" | Add-Content -Path $summaryOutput
    "Error: $_" | Add-Content -Path $summaryOutput
    "Result: FAILED" | Set-Content -Path $completionMarker
    Write-Host ""
    Write-Host "Result: FAILED"
    Write-Host $_
    throw
}
