$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$configPath = Join-Path $repoRoot "tests\scripts\config\test-script-settings.json"
$localConfigPath = Join-Path $repoRoot "tests\scripts\config\test-script-settings.local.json"
$settings = Get-Content -Path $configPath -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $localConfigPath) {
    $localSettings = Get-Content -Path $localConfigPath -Raw | ConvertFrom-Json
    foreach ($section in @("evidenceFolders", "moduleFolders", "scriptFolders")) {
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

$moduleRoot = Resolve-ConfiguredPath $settings.moduleFolders.FileValidation
$evidenceDir = Resolve-ConfiguredPath $settings.evidenceFolders.M3M4MergedModule
$scriptDir = Resolve-ConfiguredPath $settings.scriptFolders.M3M4FileValidationIngestion
$date = "2026-05-26"

New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null

function Invoke-EvidenceCommand {
    param(
        [string] $Name,
        [string] $WorkingDirectory,
        [string] $Command,
        [string] $OutputFile
    )

    Write-Host ""
    Write-Host "=== $Name ==="
    Write-Host "Working directory: $WorkingDirectory"
    Write-Host "Command: $Command"

    Push-Location $WorkingDirectory
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

Write-Host "Merged File Validation and Ingestion Module evidence run"
Write-Host "Result files: $evidenceDir"

Invoke-EvidenceCommand `
    -Name "Merged module tests" `
    -WorkingDirectory $moduleRoot `
    -Command "pytest tests -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-file-intake" `
    -OutputFile (Join-Path $evidenceDir "merged-file-intake-test-raw-output-$date.txt")

if ($env:STATS_TESTDATA_DIR) {
    Invoke-EvidenceCommand `
        -Name "Real PDF intake test" `
        -WorkingDirectory $moduleRoot `
        -Command "pytest tests\test_real_pdf_intake.py -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-file-intake-real-pdf" `
        -OutputFile (Join-Path $evidenceDir "merged-file-intake-real-pdf-test-raw-output-$date.txt")
}
else {
    Write-Host ""
    Write-Host "Skipping real PDF intake test because STATS_TESTDATA_DIR is not set."
}

Invoke-EvidenceCommand `
    -Name "Live merged API check" `
    -WorkingDirectory $moduleRoot `
    -Command "python $scriptDir\merged_file_intake_terminal_check.py" `
    -OutputFile (Join-Path $evidenceDir "merged-file-intake-terminal-check-raw-output-$date.txt")

Invoke-EvidenceCommand `
    -Name "M2 orchestration regression" `
    -WorkingDirectory $repoRoot `
    -Command "pytest tests\integration\test_stats_web_orchestration_config.py -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-m2" `
    -OutputFile (Join-Path $evidenceDir "merged-file-intake-m2-orchestration-regression-raw-output-$date.txt")

Invoke-EvidenceCommand `
    -Name "M1 identity regression" `
    -WorkingDirectory $repoRoot `
    -Command "pytest modules\identity-access-module -p no:cacheprovider --basetemp $evidenceDir\pytest-tmp-m1" `
    -OutputFile (Join-Path $evidenceDir "merged-file-intake-m1-identity-regression-raw-output-$date.txt")

Invoke-EvidenceCommand `
    -Name "Stats Web build regression" `
    -WorkingDirectory $repoRoot `
    -Command "dotnet build apps\stats-web\stats.Web.csproj -o $evidenceDir\stats-web-evidence-check" `
    -OutputFile (Join-Path $evidenceDir "merged-file-intake-stats-web-build-raw-output-$date.txt")

Write-Host ""
Write-Host "Result: PASSED"
