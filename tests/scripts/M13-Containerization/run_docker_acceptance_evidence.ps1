# M13 - Containerization Start
# Docker acceptance evidence script for M13.
# Starts the full Stats runtime stack, verifies container health, and parses every
# supported test-input fixture through M5 inside Docker. Local pytest remains for
# fast unit/static checks; this script is the acceptance/evidence path.
# M13 End

param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\.." | Select-Object -ExpandProperty Path),
    [string]$ComposeFile = "infrastructure\compose\stats-runtime.compose.yml",
    [string]$EnvFile = "infrastructure\compose\.env.container",
    [string]$TestInputDir = "test-input",
    [string]$EvidenceDir = "test-results\M13-Containerization",
    [string]$StatsWebUrl = "http://127.0.0.1:8080",
    [int]$StartupTimeoutSeconds = 180,
    [int]$HealthPollIntervalSeconds = 5,
    [switch]$LeaveStackRunning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Date = Get-Date -Format "yyyy-MM-dd"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$ComposeFilePath = Join-Path $ProjectRoot $ComposeFile
$EnvFilePath = Join-Path $ProjectRoot $EnvFile
$TestInputPath = Join-Path $ProjectRoot $TestInputDir
$EvidenceDirFull = Join-Path $ProjectRoot $EvidenceDir
$ResultFile = Join-Path $EvidenceDirFull "M13-docker-acceptance-results-$Date.txt"
$JsonDir = Join-Path $EvidenceDirFull "json-$Date"
$StatsContainer = "stats-runtime"
$DbContainer = "stats-db"
$ContainerInputDir = "/tmp/m13-test-input"

if (-not (Test-Path $EvidenceDirFull)) {
    New-Item -ItemType Directory -Path $EvidenceDirFull -Force | Out-Null
}
if (-not (Test-Path $JsonDir)) {
    New-Item -ItemType Directory -Path $JsonDir -Force | Out-Null
}

$Results = [System.Collections.Generic.List[string]]::new()
$Passed = 0
$Failed = 0

function Write-Result {
    param([string]$Line)
    $Results.Add($Line)
    Write-Host $Line
}

function Write-Block {
    param([string]$Text)
    foreach ($line in ($Text -split "`r?`n")) {
        Write-Result $line
    }
}

function Pass {
    param([string]$Label)
    $script:Passed++
    Write-Result "  [PASS] $Label"
}

function Fail {
    param([string]$Label, [string]$Detail = "")
    $script:Failed++
    $msg = "  [FAIL] $Label"
    if ($Detail) { $msg += " -- $Detail" }
    Write-Result $msg
}

function Section {
    param([string]$Title)
    Write-Result ""
    Write-Result "=== $Title ==="
}

function Stop-WithResults {
    param([int]$ExitCode)
    $Results | Set-Content -Path $ResultFile -Encoding UTF8
    Write-Host ""
    Write-Host "Results written to: $ResultFile"
    exit $ExitCode
}

function Get-JsonProperty {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Safe-FileStem {
    param([string]$Name)
    return ($Name -replace '[^A-Za-z0-9._-]', '_')
}

Write-Result "M13 Docker Acceptance Evidence"
Write-Result "Run at: $Timestamp"
Write-Result "Project root: $ProjectRoot"
Write-Result "Compose file: $ComposeFilePath"
Write-Result "Env file: $EnvFilePath"
Write-Result "Stats Web URL: $StatsWebUrl"
Write-Result "Test input dir: $TestInputPath"
Write-Result "Per-file JSON dir: $JsonDir"

Section "1. Prerequisites"

if (Test-Path $ComposeFilePath) { Pass "Compose file exists" } else { Fail "Compose file exists" $ComposeFilePath }
if (Test-Path $EnvFilePath) { Pass "container env file exists" } else { Fail "container env file exists" $EnvFilePath }
if (Test-Path $TestInputPath) { Pass "test-input directory exists" } else { Fail "test-input directory exists" $TestInputPath }

$SupportedExtensions = @(".jpg", ".jpeg", ".png", ".pdf")
$FixtureFiles = @()
if (Test-Path $TestInputPath) {
    $FixtureFiles = Get-ChildItem -LiteralPath $TestInputPath -File | Where-Object {
        $SupportedExtensions -contains $_.Extension.ToLower()
    } | Sort-Object Name
}

if ($FixtureFiles.Count -gt 0) {
    Pass "test-input contains $($FixtureFiles.Count) supported fixture file(s)"
    foreach ($fixture in $FixtureFiles) {
        Write-Result "     - $($fixture.Name) ($($fixture.Length) bytes)"
    }
} else {
    Fail "test-input must contain at least one JPG, JPEG, PNG, or PDF fixture"
}

if ($Failed -gt 0) {
    Write-Result ""
    Write-Result "PREREQUISITES NOT MET."
    Stop-WithResults 1
}

Section "2. Start Docker Compose stack"

$ComposeArgs = @("--file", $ComposeFilePath, "--env-file", $EnvFilePath, "up", "--build", "--detach")
Write-Result "  Running: docker compose $($ComposeArgs -join ' ')"
Push-Location $ProjectRoot
try {
    $ComposeOutput = docker compose @ComposeArgs 2>&1
    Write-Block ($ComposeOutput -join "`n")
    if ($LASTEXITCODE -eq 0) {
        Pass "docker compose up --build --detach exited 0"
    } else {
        Fail "docker compose up --build --detach" "exit code $LASTEXITCODE"
        Stop-WithResults 1
    }
} finally {
    Pop-Location
}

Section "3. Wait for Stats Web health"

$Elapsed = 0
$StatsWebHealthy = $false
while ($Elapsed -lt $StartupTimeoutSeconds) {
    try {
        $Response = Invoke-WebRequest -Uri "$StatsWebUrl/health" -TimeoutSec 5 -UseBasicParsing
        if ($Response.StatusCode -eq 200) {
            $StatsWebHealthy = $true
            break
        }
    } catch {
        Start-Sleep -Seconds $HealthPollIntervalSeconds
        $Elapsed += $HealthPollIntervalSeconds
        Write-Result "  waiting... ${Elapsed}s"
    }
}

if ($StatsWebHealthy) {
    Pass "Stats Web /health responded 200"
} else {
    Fail "Stats Web /health did not become healthy within ${StartupTimeoutSeconds}s"
    Stop-WithResults 1
}

Section "4. Public and internal health checks"

try {
    $StatsHealth = Invoke-RestMethod -Uri "$StatsWebUrl/health" -TimeoutSec 10
    $StatsHealthJson = $StatsHealth | ConvertTo-Json -Depth 20
    Write-Result "Stats Web health JSON:"
    Write-Block $StatsHealthJson
    if ($StatsHealth.status -eq "healthy") { Pass "Stats Web status is healthy" } else { Fail "Stats Web status" $StatsHealth.status }
} catch {
    Fail "Stats Web /health JSON" $_.Exception.Message
}

$ModuleApis = @(
    @{ Name = "Identity Access API"; Port = 8013 },
    @{ Name = "File Validation API"; Port = 8014 },
    @{ Name = "Document Parsing API"; Port = 8015 }
)

foreach ($Api in $ModuleApis) {
    $Output = docker exec $StatsContainer curl -sf "http://localhost:$($Api.Port)/health" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Pass "$($Api.Name) health reachable inside $StatsContainer"
        Write-Result "$($Api.Name) health JSON:"
        Write-Block ($Output -join "`n")
        if ($Api.Port -eq 8015) {
            try {
                $ParsedHealth = ($Output -join "`n") | ConvertFrom-Json
                if ($ParsedHealth.ocr.enabled -eq $true) { Pass "Document Parsing reports ocr.enabled=true" } else { Fail "Document Parsing ocr.enabled" "$($ParsedHealth.ocr.enabled)" }
                if ($ParsedHealth.ocr.tesseract_available -eq $true) { Pass "Document Parsing reports tesseract_available=true" } else { Fail "Document Parsing tesseract_available" "$($ParsedHealth.ocr.tesseract_available)" }
                if ($ParsedHealth.ocr.renderer_available -eq $true) { Pass "Document Parsing reports renderer_available=true" } else { Fail "Document Parsing renderer_available" "$($ParsedHealth.ocr.renderer_available)" }
            } catch {
                Fail "Document Parsing health JSON parse" $_.Exception.Message
            }
        }
    } else {
        Fail "$($Api.Name) health inside $StatsContainer" "exit code $LASTEXITCODE"
        Write-Block ($Output -join "`n")
    }
}

Section "5. stats-db schema check"

$PgOutput = docker exec $DbContainer psql -U stats -d stats -c "SELECT count(*) AS users_table_count FROM information_schema.tables WHERE table_schema='public' AND table_name='users';" 2>&1
Write-Block ($PgOutput -join "`n")
if ($LASTEXITCODE -eq 0 -and (($PgOutput -join "`n") -match "\b1\b")) {
    Pass "stats-db public.users table exists"
} else {
    Fail "stats-db public.users table exists" "psql exit code $LASTEXITCODE"
}

Section "6. M5 OCR parse for every test-input fixture"

docker exec $StatsContainer mkdir -p $ContainerInputDir | Out-Null

foreach ($Fixture in $FixtureFiles) {
    $FileName = $Fixture.Name
    $Ext = $Fixture.Extension.ToLower()
    $ContainerDest = "$ContainerInputDir/$FileName"
    $SafeName = Safe-FileStem $FileName
    $JsonFile = Join-Path $JsonDir "$SafeName.json"

    Write-Result ""
    Write-Result "Fixture: $FileName"
    Write-Result "Source: $($Fixture.FullName)"
    Write-Result "Container: ${StatsContainer}:${ContainerDest}"

    $CopyOutput = docker cp $Fixture.FullName "${StatsContainer}:${ContainerDest}" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "$FileName copied into $StatsContainer" "exit code $LASTEXITCODE"
        Write-Block ($CopyOutput -join "`n")
        continue
    }
    Pass "$FileName copied into $StatsContainer"

    $CurlCmd = "curl -sS -f -X POST http://localhost:8015/api/v1/parses -F `"file=@$ContainerDest`" -F `"allow_ocr_fallback=true`" -F `"page_limit=1`" -F `"classification_threshold=0.1`""
    if ($Ext -eq ".pdf") {
        $CurlCmd += " -F `"allow_direct_text=false`""
    }

    $ExecOutput = docker exec $StatsContainer sh -lc $CurlCmd 2>&1
    $RawJson = $ExecOutput -join "`n"
    if ($LASTEXITCODE -ne 0) {
        Fail "$FileName parsed through M5 inside Docker" "curl exit code $LASTEXITCODE"
        Write-Block $RawJson
        continue
    }

    try {
        $ParseResult = $RawJson | ConvertFrom-Json
        $PrettyJson = $ParseResult | ConvertTo-Json -Depth 50
        $PrettyJson | Set-Content -Path $JsonFile -Encoding UTF8

        Write-Result "JSON for ${FileName}:"
        Write-Block $PrettyJson
        Write-Result "JSON file: $JsonFile"

        $Status = Get-JsonProperty $ParseResult "status"
        $Text = Get-JsonProperty $ParseResult "text"
        $TextLen = if ($null -ne $Text) { $Text.Length } else { 0 }
        $StrategyObject = Get-JsonProperty $ParseResult "strategy"
        $MetadataObject = Get-JsonProperty $ParseResult "metadata"
        $Strategy = Get-JsonProperty $StrategyObject "selected_strategy"
        $Method = Get-JsonProperty $MetadataObject "extraction_method"

        Write-Result "Summary: status=$Status; strategy=$Strategy; method=$Method; text_length=$TextLen"

        if ($Status -eq "completed" -or $Status -eq "completed_with_warnings") {
            Pass "$FileName status is $Status"
        } else {
            Fail "$FileName status" "expected completed/completed_with_warnings, got $Status"
        }

        if ($Ext -eq ".jpg" -or $Ext -eq ".jpeg" -or $Ext -eq ".png") {
            if ($Strategy -eq "tesseract_ocr") { Pass "$FileName strategy is tesseract_ocr" } else { Fail "$FileName strategy" "expected tesseract_ocr, got $Strategy" }
        }

        if ($Ext -eq ".pdf") {
            if ($Method -eq "ocr") { Pass "$FileName PDF extraction method is ocr" } else { Fail "$FileName PDF extraction method" "expected ocr, got $Method" }
        }

        if ($TextLen -gt 0) {
            Pass "$FileName extracted text is non-empty ($TextLen chars)"
        } else {
            Fail "$FileName extracted text is non-empty" "text_length=0"
        }
    } catch {
        Fail "$FileName JSON parse" $_.Exception.Message
        Write-Block $RawJson
    }
}

Section "7. Container logs snapshot"

$Logs = docker compose --file $ComposeFilePath logs --tail=40 stats 2>&1
Write-Block ($Logs -join "`n")
if ($LASTEXITCODE -eq 0) { Pass "container logs collected" } else { Fail "container logs collected" "exit code $LASTEXITCODE" }

if (-not $LeaveStackRunning) {
    Section "8. Teardown"
    $DownOutput = docker compose --file $ComposeFilePath down 2>&1
    Write-Block ($DownOutput -join "`n")
    if ($LASTEXITCODE -eq 0) { Pass "docker compose down completed" } else { Fail "docker compose down" "exit code $LASTEXITCODE" }
} else {
    Write-Result ""
    Write-Result "Stack left running because -LeaveStackRunning was set."
}

Section "Summary"
$Total = $Passed + $Failed
Write-Result "Total:  $Total"
Write-Result "Passed: $Passed"
Write-Result "Failed: $Failed"
if ($Failed -eq 0) {
    Write-Result "Result: PASSED"
} else {
    Write-Result "Result: FAILED"
}
Write-Result "Evidence written to: $ResultFile"
Write-Result "Per-file JSON written to: $JsonDir"

$Results | Set-Content -Path $ResultFile -Encoding UTF8

if ($Failed -gt 0) {
    exit 1
}
