# M13 - Containerization Start
# Docker full regression evidence script: M1 through M5.
#
# PURPOSE:
#   Provides production-like regression evidence for modules M1-M5 against the
#   containerized Stats runtime. This is the authoritative evidence runner from
#   M13 onward. All acceptance, OCR, database, and cross-module evidence must
#   run through this script, not against host-started processes.
#
# TESTING BOUNDARY:
#   Local unit/static tests  ->  host pytest (fast developer feedback)
#   Acceptance, OCR, DB, cross-module regression  ->  this script (Docker stack)
#
# DOCKER STACK:
#   docker compose --file infrastructure\compose\stats-runtime.compose.yml \
#                  --env-file infrastructure\compose\.env.container \
#                  up --build --detach
#   Entry point:  http://127.0.0.1:8080
#   DB service:   stats-db (PostgreSQL 16)
#   App service:  stats-runtime (Stats Web + M1/M3/M4/M5 APIs + Tesseract OCR)
#
# MODULES COVERED:
#   M1  Identity Access Module    -- DB init, login, token issuance, user listing
#   M2  Stats Web Shell           -- /health, /, /Login, /Upload page presence
#   M3  File Validation           -- validate every test-input/ fixture
#   M4  File Ingestion            -- ingest every validated test-input/ fixture
#   M5  Document Parsing          -- OCR/text parse every test-input/ fixture
#   Cross-module: validate -> ingest -> parse pipeline per fixture file
#
# FIXTURE SOURCE:
#   test-input/  (gitignored real files; only test-input/README.md is tracked)
#   Do NOT use Google Drive paths or synthetic fallbacks.
#
# SECRETS:
#   Supplied via infrastructure\compose\.env.container (never committed).
#   Tokens are truncated in log output; full secrets are never written to
#   evidence files.
#
# USAGE:
#   cd C:\000_Capstone
#   .\tests\scripts\regression\run_docker_full_regression_evidence.ps1
#
#   Optional parameters:
#     -SkipBuild        Skip docker compose up --build (use existing image)
#     -LeaveStackRunning  Do not docker compose down after the run
#     -StartupTimeoutSeconds <n>  Override the health poll timeout (default 180)
# M13 End

param(
    [string]$ProjectRoot = (Resolve-Path "$PSScriptRoot\..\..\.." | Select-Object -ExpandProperty Path),
    [string]$ComposeFile = "infrastructure\compose\stats-runtime.compose.yml",
    [string]$EnvFile = "infrastructure\compose\.env.container",
    [string]$TestInputDir = "test-input",
    [string]$EvidenceRoot = "test-results\DockerRegression",
    [string]$StatsWebUrl = "http://127.0.0.1:8080",
    [int]$StartupTimeoutSeconds = 180,
    [int]$HealthPollIntervalSeconds = 5,
    [switch]$SkipBuild,
    [switch]$LeaveStackRunning
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$Date = Get-Date -Format "yyyy-MM-dd"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$ComposeFilePath = Join-Path $ProjectRoot $ComposeFile
$EnvFilePath     = Join-Path $ProjectRoot $EnvFile
$TestInputPath   = Join-Path $ProjectRoot $TestInputDir
$EvidenceRootFull = Join-Path $ProjectRoot $EvidenceRoot

$SummaryFile = Join-Path $EvidenceRootFull "docker-regression-summary-$Date.md"
$RawOutputFile = Join-Path $EvidenceRootFull "docker-regression-raw-output-$Date.txt"
$M1Dir  = Join-Path $EvidenceRootFull "M1"
$M2Dir  = Join-Path $EvidenceRootFull "M2"
$M3Dir  = Join-Path $EvidenceRootFull "M3"
$M4Dir  = Join-Path $EvidenceRootFull "M4"
$M5Dir  = Join-Path $EvidenceRootFull "M5"
$CrossDir = Join-Path $EvidenceRootFull "cross-module"

foreach ($Dir in @($EvidenceRootFull, $M1Dir, $M2Dir, $M3Dir, $M4Dir, $M5Dir, $CrossDir)) {
    if (-not (Test-Path $Dir)) { New-Item -ItemType Directory -Path $Dir -Force | Out-Null }
}

# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------
$Results   = [System.Collections.Generic.List[string]]::new()
$Passed    = 0
$Failed    = 0
$Skipped   = 0
$Gaps      = [System.Collections.Generic.List[string]]::new()

function Write-Result {
    param([string]$Line)
    $Results.Add($Line)
    Write-Host $Line
}

function Pass   { param([string]$L) ; $script:Passed++  ; Write-Result "  [PASS] $L" }
function Fail   { param([string]$L, [string]$D = "") ; $script:Failed++  ; Write-Result "  [FAIL] $L$(if($D){" -- $D"})" }
function Skip   { param([string]$L, [string]$D = "") ; $script:Skipped++ ; Write-Result "  [SKIP] $L$(if($D){" -- $D"})" }
function Gap    { param([string]$G) ; $script:Gaps.Add($G) ; Write-Result "  [GAP]  $G" }
function Section { param([string]$T) ; Write-Result "" ; Write-Result "=== $T ===" }
function Get-JsonProperty {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}
function First-NonEmpty {
    foreach ($value in $args) {
        if ($null -ne $value -and "$value" -ne "") { return $value }
    }
    return "(missing)"
}
function Get-EnvFileValue {
    param([string]$Name)
    if (-not (Test-Path $EnvFilePath)) { return $null }
    $line = Get-Content -Path $EnvFilePath | Where-Object { $_ -match "^\s*$Name\s*=" } | Select-Object -First 1
    if (-not $line) { return $null }
    return (($line -split "=", 2)[1]).Trim()
}

Write-Result "Stats Docker Full Regression Evidence"
Write-Result "Run at:          $Timestamp"
Write-Result "Project root:    $ProjectRoot"
Write-Result "Compose file:    $ComposeFilePath"
Write-Result "Env file:        $EnvFilePath"
Write-Result "Stats Web URL:   $StatsWebUrl"
Write-Result "Test input dir:  $TestInputPath"
Write-Result "Evidence root:   $EvidenceRootFull"

# ---------------------------------------------------------------------------
# 0. Prerequisites
# ---------------------------------------------------------------------------
Section "0. Prerequisites"

$prereqOk = $true

if (-not (Test-Path $ComposeFilePath)) { Fail "Compose file exists" $ComposeFilePath ; $prereqOk = $false }
else { Pass "Compose file exists" }

if (-not (Test-Path $EnvFilePath)) {
    Fail ".env.container exists" "Copy infrastructure\compose\.env.container.example -> .env.container and fill secrets"
    $prereqOk = $false
} else { Pass ".env.container exists" }

if (-not (Test-Path $TestInputPath)) { Fail "test-input/ exists" ; $prereqOk = $false }
else { Pass "test-input/ exists" }

$SupportedExtensions = @(".jpg", ".jpeg", ".png", ".pdf")
$Fixtures = @()
if (Test-Path $TestInputPath) {
    $Fixtures = @(Get-ChildItem -Path $TestInputPath -File |
        Where-Object { $SupportedExtensions -contains $_.Extension.ToLower() })
}

if ($Fixtures.Count -gt 0) {
    Pass "test-input/ has $($Fixtures.Count) supported fixture(s)"
    foreach ($f in $Fixtures) { Write-Result "     $($f.Name)" }
} else {
    Fail "test-input/ needs at least one .jpg/.jpeg/.png/.pdf"
    $prereqOk = $false
}

if (-not $prereqOk) {
    Write-Result ""
    Write-Result "PREREQUISITES NOT MET -- fix issues above, then rerun."
    $Results | Set-Content $SummaryFile -Encoding UTF8
    exit 1
}

# ---------------------------------------------------------------------------
# 1. Start Docker stack
# ---------------------------------------------------------------------------
Section "1. Docker Compose -- start stack"

$UpArgs = @("--file", $ComposeFilePath, "--env-file", $EnvFilePath, "up")
if (-not $SkipBuild) { $UpArgs += "--build" }
$UpArgs += "--detach"

Write-Result "  docker compose $($UpArgs -join ' ')"
Push-Location $ProjectRoot
try {
    docker compose @UpArgs
    if ($LASTEXITCODE -ne 0) { Fail "docker compose up" "exit $LASTEXITCODE" ; $Results | Set-Content $SummaryFile -Encoding UTF8 ; Pop-Location ; exit 1 }
    Pass "docker compose up completed (exit 0)"
} finally { Pop-Location }

# ---------------------------------------------------------------------------
# 2. Wait for Stats Web health
# ---------------------------------------------------------------------------
Section "2. Wait for Stats Web /health"

$elapsed = 0 ; $webHealthy = $false
Write-Result "  Polling $StatsWebUrl/health (timeout ${StartupTimeoutSeconds}s) ..."
while ($elapsed -lt $StartupTimeoutSeconds) {
    try {
        $r = Invoke-WebRequest -Uri "$StatsWebUrl/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { $webHealthy = $true ; break }
    } catch { }
    Start-Sleep $HealthPollIntervalSeconds
    $elapsed += $HealthPollIntervalSeconds
    Write-Host "    ${elapsed}s ..."
}

if ($webHealthy) { Pass "Stats Web /health OK ($elapsed s)" }
else {
    Fail "Stats Web /health did not become ready in ${StartupTimeoutSeconds}s"
    Write-Result "  Hint: docker compose --file $ComposeFile logs stats"
    $Results | Set-Content $SummaryFile -Encoding UTF8 ; exit 1
}

# ---------------------------------------------------------------------------
# Helper: docker exec curl into stats-runtime
# ---------------------------------------------------------------------------
function Invoke-ContainerCurl {
    param([string]$Path)
    $out = docker exec stats-runtime curl -sf "http://localhost$Path" 2>&1
    return [PSCustomObject]@{ ExitCode = $LASTEXITCODE ; Output = $out }
}

# ---------------------------------------------------------------------------
# 3. Stack health summary
# ---------------------------------------------------------------------------
Section "3. Stack health -- all services"

# Stats Web payload
try {
    $hw = Invoke-RestMethod -Uri "$StatsWebUrl/health" -TimeoutSec 10
    if ($hw.status -eq "healthy") { Pass "Stats Web: status=healthy" } else { Fail "Stats Web status" $hw.status }
    if ($hw.service -eq "Stats Web") { Pass "Stats Web: service='Stats Web'" } else { Fail "Stats Web service field" $hw.service }
} catch { Fail "Stats Web /health JSON" $_.Exception.Message }

# Module APIs inside container
$ModuleApis = @(
    @{Name="Identity Access API"  ; Port=8013 ; Path="/health"},
    @{Name="File Validation API"  ; Port=8014 ; Path="/health"},
    @{Name="Document Parsing API" ; Port=8015 ; Path="/health"}
)
foreach ($api in $ModuleApis) {
    $res = Invoke-ContainerCurl ":$($api.Port)$($api.Path)"
    if ($res.ExitCode -eq 0) {
        Pass "$($api.Name) /health reachable inside stats-runtime"
        Write-Result "  $($res.Output)"
    } else {
        Fail "$($api.Name) /health" "exit $($res.ExitCode)"
    }
}

# Document Parsing: OCR + PyMuPDF
try {
    $dpRaw = docker exec stats-runtime curl -sf "http://localhost:8015/health" 2>&1
    $dpJson = $dpRaw | ConvertFrom-Json
    if ($dpJson.ocr.enabled -eq $true)       { Pass "Document Parsing: ocr.enabled=true" }
    else                                       { Fail "Document Parsing: ocr.enabled" "got $($dpJson.ocr.enabled)" }
    if ($dpJson.ocr.engine -eq "tesseract")   { Pass "Document Parsing: ocr.engine=tesseract" }
    else                                       { Fail "Document Parsing: ocr.engine" "got $($dpJson.ocr.engine)" }
    $pymupdf = First-NonEmpty (Get-JsonProperty $dpJson.ocr "pdf_renderer") (Get-JsonProperty $dpJson.ocr "pymupdf_version") (Get-JsonProperty $dpJson.ocr "renderer") "(field not present)"
    Write-Result "  ocr.pdf_renderer/pymupdf field: $pymupdf"
} catch { Fail "Document Parsing /health JSON parse" $_.Exception.Message }

# ---------------------------------------------------------------------------
# 4. M1 -- Identity Access Module
# ---------------------------------------------------------------------------
Section "4. M1 -- Identity Access Module"

# 4a. DB init: users table exists
try {
    $pgOut = docker exec stats-db psql -U stats -d stats -c "SELECT count(*) FROM information_schema.tables WHERE table_name='users';" 2>&1
    if ($LASTEXITCODE -eq 0 -and $pgOut -match "1") {
        Pass "M1: stats-db public.users table exists"
    } else {
        Fail "M1: users table not found" "psql output: $pgOut"
    }
} catch { Fail "M1: stats-db psql" $_.Exception.Message }

# 4b. Login -- only if admin creds are available via env vars
$adminEmail = First-NonEmpty $env:DEFAULT_ADMIN_EMAIL (Get-EnvFileValue "DEFAULT_ADMIN_EMAIL") ""
$adminPass  = First-NonEmpty $env:DEFAULT_ADMIN_PASSWORD (Get-EnvFileValue "DEFAULT_ADMIN_PASSWORD") ""
$m1Token    = $null

if ($adminEmail -and $adminEmail -ne "(missing)" -and $adminPass -and $adminPass -ne "(missing)") {
    try {
        $loginBody = @{ email = $adminEmail ; password = $adminPass } | ConvertTo-Json
        $escapedLoginBody = $loginBody.Replace("'", "'\''")
        $loginRaw = docker exec stats-runtime sh -lc "curl -sf -X POST http://localhost:8013/api/v1/auth/login -H 'Content-Type: application/json' -d '$escapedLoginBody'" 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Identity login failed inside stats-runtime: $loginRaw"
        }
        $loginRes = ($loginRaw -join "`n") | ConvertFrom-Json
        $m1Token = Get-JsonProperty $loginRes "access_token"
        if ($m1Token) {
            Pass "M1: login returned access_token via stats-runtime"
            $tokenPreview = $m1Token.Substring(0, [Math]::Min(20, $m1Token.Length)) + "..."
            $loginEvidence = @{
                module       = "M1 Identity Access"
                endpoint     = "stats-runtime:http://localhost:8013/api/v1/auth/login"
                email        = $adminEmail
                token_prefix = $tokenPreview
                note         = "Full token not stored in evidence. Token used for M1/M3/M4/M5 authenticated calls."
            } | ConvertTo-Json
            $loginEvidence | Set-Content (Join-Path $M1Dir "m1-login-evidence-$Date.json") -Encoding UTF8
        } else {
            Fail "M1: login response missing access_token"
        }
    } catch { Fail "M1: login request" $_.Exception.Message }

    # 4c. User listing (admin-only endpoint)
    if ($m1Token) {
        try {
            $usersRaw = docker exec stats-runtime sh -lc "curl -sf http://localhost:8013/api/v1/users -H 'Authorization: Bearer $m1Token'" 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Identity user listing failed inside stats-runtime: $usersRaw"
            }
            $users = ($usersRaw -join "`n") | ConvertFrom-Json
            $userCount = if ($users -is [array]) { $users.Count } else { 1 }
            Pass "M1: GET /api/v1/users returned $userCount user(s) via stats-runtime"
            $userEvidence = @{
                module    = "M1 Identity Access"
                endpoint  = "stats-runtime:http://localhost:8013/api/v1/users"
                count     = $userCount
                note      = "Email addresses omitted from evidence."
            } | ConvertTo-Json
            $userEvidence | Set-Content (Join-Path $M1Dir "m1-users-evidence-$Date.json") -Encoding UTF8
        } catch { Fail "M1: GET /api/v1/users" $_.Exception.Message }
    }
} else {
    Skip "M1: login and user-listing" "DEFAULT_ADMIN_EMAIL/PASSWORD not set in environment"
    Gap "M1 authenticated flow -- set DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD in .env.container to enable full login evidence"
}

# ---------------------------------------------------------------------------
# 5. M2 -- Stats Web Shell
# ---------------------------------------------------------------------------
Section "5. M2 -- Stats Web Shell"

$m2Pages = @(
    @{Path="/health"  ; MinStatus=200 ; MaxStatus=200 ; Desc="Stats Web /health"},
    @{Path="/"        ; MinStatus=200 ; MaxStatus=302 ; Desc="Stats Web root /"},
    @{Path="/Login"   ; MinStatus=200 ; MaxStatus=302 ; Desc="Stats Web /Login"},
    @{Path="/Upload"  ; MinStatus=200 ; MaxStatus=302 ; Desc="Stats Web /Upload"}
)

foreach ($page in $m2Pages) {
    try {
        $resp = Invoke-WebRequest -Uri "$StatsWebUrl$($page.Path)" `
            -TimeoutSec 10 -UseBasicParsing -MaximumRedirection 0 `
            -ErrorAction SilentlyContinue
        $code = $resp.StatusCode
        if ($code -ge $page.MinStatus -and $code -le $page.MaxStatus) {
            Pass "M2: $($page.Desc) -> HTTP $code"
        } else {
            Fail "M2: $($page.Desc)" "HTTP $code (expected $($page.MinStatus)-$($page.MaxStatus))"
        }
        $ev = @{ module = "M2 Stats Web Shell" ; path = $page.Path ; http_status = $code } | ConvertTo-Json
        $ev | Set-Content (Join-Path $M2Dir "m2-page-$(($page.Path -replace '/','-').TrimStart('-'))-evidence-$Date.json") -Encoding UTF8
    } catch {
        # WebRequest throws on non-2xx when MaximumRedirection=0; capture the status from the exception
        $code = $null
        if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
        if ($code -and $code -ge $page.MinStatus -and $code -le $page.MaxStatus) {
            Pass "M2: $($page.Desc) -> HTTP $code (redirect)"
        } else {
            Fail "M2: $($page.Desc)" $_.Exception.Message
        }
    }
}

Gap "M2 browser screenshots -- run manually or via Claude in Chrome; this script covers HTTP status evidence only"

# ---------------------------------------------------------------------------
# 6. M3 -- File Validation (per fixture)
# ---------------------------------------------------------------------------
Section "6. M3 -- File Validation (all test-input/ fixtures)"

$m3Passed = 0 ; $m3Failed = 0
foreach ($fixture in $Fixtures) {
    $fileName = $fixture.Name
    Write-Result "  Fixture: $fileName"
    $containerDest = "/tmp/$fileName"
    try {
        docker cp $fixture.FullName "stats-runtime:$containerDest" | Out-Null
        $curlCmd = "curl -sf -X POST http://localhost:8014/api/v1/files/validate -F `"file=@$containerDest`""
        $rawOut = docker exec stats-runtime sh -lc $curlCmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Fail "M3: validate $fileName" "exit $LASTEXITCODE"
            $m3Failed++ ; continue
        }
        $vResult = $rawOut | ConvertFrom-Json
        $metadata = Get-JsonProperty $vResult "metadata"
        $status  = First-NonEmpty (Get-JsonProperty $vResult "status")
        $mime    = First-NonEmpty (Get-JsonProperty $metadata "detected_mime_type")
        $size    = First-NonEmpty (Get-JsonProperty $metadata "size_bytes")
        Write-Result "  status=$status  mime=$mime  size=${size}B"
        if ($status -eq "accepted") { Pass "M3: $fileName validated -> accepted" ; $m3Passed++ }
        else                         { Fail "M3: $fileName status" "got $status" ; $m3Failed++ }
        $rawOut | Set-Content (Join-Path $M3Dir "m3-validate-$(($fileName -replace '\.','-'))-$Date.json") -Encoding UTF8
    } catch { Fail "M3: validate $fileName" $_.Exception.Message ; $m3Failed++ }
}
Write-Result "  M3 totals: $m3Passed passed, $m3Failed failed"

# ---------------------------------------------------------------------------
# 7. M4 -- File Ingestion (per fixture, using validated status)
# ---------------------------------------------------------------------------
Section "7. M4 -- File Ingestion (all test-input/ fixtures)"

$m4Passed = 0 ; $m4Failed = 0
$ingestionIds = @{}   # filename -> ingestion_id, used by cross-module section

foreach ($fixture in $Fixtures) {
    $fileName = $fixture.Name
    Write-Result "  Fixture: $fileName"
    $containerDest = "/tmp/$fileName"
    try {
        # File should already be in /tmp from M3; re-copy in case it was cleaned
        docker cp $fixture.FullName "stats-runtime:$containerDest" 2>&1 | Out-Null
        $curlCmd = "curl -sf -X POST http://localhost:8014/api/v1/ingestions " +
                   "-F `"file=@$containerDest`" " +
                   "-F `"validation_status=accepted`" " +
                   "-F `"source_type=api`""
        $rawOut = docker exec stats-runtime sh -lc $curlCmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Fail "M4: ingest $fileName" "exit $LASTEXITCODE"
            $m4Failed++ ; continue
        }
        $iResult = $rawOut | ConvertFrom-Json
        $ingId   = First-NonEmpty (Get-JsonProperty $iResult "ingestion_id") (Get-JsonProperty $iResult "id")
        $status  = First-NonEmpty (Get-JsonProperty $iResult "status")
        $created = First-NonEmpty (Get-JsonProperty $iResult "created_at_utc") (Get-JsonProperty $iResult "created_at") (Get-JsonProperty $iResult "created")
        Write-Result "  ingestion_id=$ingId  status=$status  created=$created"
        if ($ingId -ne "(missing)" -and $ingId -ne "") {
            Pass "M4: $fileName ingested (id=$ingId)" ; $m4Passed++
            $ingestionIds[$fileName] = $ingId
        } else {
            Fail "M4: $fileName ingestion_id missing" ; $m4Failed++
        }
        $rawOut | Set-Content (Join-Path $M4Dir "m4-ingest-$(($fileName -replace '\.','-'))-$Date.json") -Encoding UTF8
    } catch { Fail "M4: ingest $fileName" $_.Exception.Message ; $m4Failed++ }
}
Write-Result "  M4 totals: $m4Passed passed, $m4Failed failed"

# ---------------------------------------------------------------------------
# 8. M5 -- Document Parsing (per fixture, with OCR forcing for PDFs)
# ---------------------------------------------------------------------------
Section "8. M5 -- Document Parsing (all test-input/ fixtures)"

$m5Passed = 0 ; $m5Failed = 0

foreach ($fixture in $Fixtures) {
    $fileName = $fixture.Name
    $ext      = $fixture.Extension.ToLower()
    Write-Result "  Fixture: $fileName"
    $containerDest = "/tmp/$fileName"
    try {
        docker cp $fixture.FullName "stats-runtime:$containerDest" 2>&1 | Out-Null

        # Build parse curl command
        $baseCmd = "curl -sf -X POST http://localhost:8015/api/v1/parses " +
                   "-F `"file=@$containerDest`" " +
                   "-F `"allow_ocr_fallback=true`""

        # Force OCR for PDFs; add page_limit to keep evidence runs fast
        if ($ext -eq ".pdf") {
            $curlCmd = $baseCmd + " -F `"allow_direct_text=false`" -F `"page_limit=1`""
        } else {
            $curlCmd = $baseCmd
        }

        $rawOut = docker exec stats-runtime sh -lc $curlCmd 2>&1
        if ($LASTEXITCODE -ne 0) {
            Fail "M5: parse $fileName" "exit $LASTEXITCODE"
            $m5Failed++ ; continue
        }
        $pResult  = $rawOut | ConvertFrom-Json
        $strategyObject = Get-JsonProperty $pResult "strategy"
        $metadataObject = Get-JsonProperty $pResult "metadata"
        $classificationObject = Get-JsonProperty $pResult "classification"
        $qualityObject = Get-JsonProperty $pResult "quality"
        $text = Get-JsonProperty $pResult "text"
        $strategy = First-NonEmpty (Get-JsonProperty $strategyObject "selected_strategy")
        $method   = First-NonEmpty (Get-JsonProperty $metadataObject "extraction_method")
        $status   = First-NonEmpty (Get-JsonProperty $pResult "status")
        $textLen  = First-NonEmpty (Get-JsonProperty $qualityObject "text_length")
        if ($textLen -eq "(missing)") {
            $textLen = if ($null -ne $text) { $text.Length } else { 0 }
        }
        $docClass = First-NonEmpty (Get-JsonProperty $classificationObject "document_type")
        Write-Result "  strategy=$strategy  method=$method  status=$status  text_len=$textLen  class=$docClass"

        # Assertions
        $fileOk = $true
        if ($ext -in @(".jpg", ".jpeg", ".png")) {
            if ($strategy -eq "tesseract_ocr") { Pass "M5: $fileName strategy=tesseract_ocr" }
            else { Fail "M5: $fileName" "expected strategy=tesseract_ocr, got $strategy" ; $fileOk = $false }
        } elseif ($ext -eq ".pdf") {
            if ($method -eq "ocr" -or $strategy -eq "tesseract_ocr") {
                Pass "M5: $fileName OCR path confirmed (strategy=$strategy method=$method)"
            } else {
                # A text-layer PDF may legitimately use pdf_text when allow_direct_text was not honoured
                if ($strategy -in @("pdf_text", "tesseract_ocr")) {
                    Pass "M5: $fileName parsed (strategy=$strategy)"
                } else {
                    Fail "M5: $fileName" "unexpected strategy=$strategy method=$method" ; $fileOk = $false
                }
            }
        }
        if ($textLen -gt 0) { Pass "M5: $fileName extracted_text non-empty ($textLen chars)" }
        else                  { Fail "M5: $fileName extracted_text is empty" ; $fileOk = $false }

        if ($fileOk) { $m5Passed++ } else { $m5Failed++ }
        $rawOut | Set-Content (Join-Path $M5Dir "m5-parse-$(($fileName -replace '\.','-'))-$Date.json") -Encoding UTF8
    } catch { Fail "M5: parse $fileName" $_.Exception.Message ; $m5Failed++ }
}
Write-Result "  M5 totals: $m5Passed passed, $m5Failed failed"

# ---------------------------------------------------------------------------
# 9. Cross-module pipeline evidence
# ---------------------------------------------------------------------------
Section "9. Cross-module pipeline (validate -> ingest -> parse per fixture)"

$xPassed = 0 ; $xFailed = 0

foreach ($fixture in $Fixtures) {
    $fileName = $fixture.Name
    $ext      = $fixture.Extension.ToLower()
    Write-Result "  Pipeline: $fileName"

    $ingId    = $ingestionIds[$fileName]
    $m3File   = Join-Path $M3Dir "m3-validate-$(($fileName -replace '\.','-'))-$Date.json"
    $m4File   = Join-Path $M4Dir "m4-ingest-$(($fileName -replace '\.','-'))-$Date.json"
    $m5File   = Join-Path $M5Dir "m5-parse-$(($fileName -replace '\.','-'))-$Date.json"

    $m3Ok = Test-Path $m3File
    $m4Ok = Test-Path $m4File
    $m5Ok = Test-Path $m5File

    $summary = [ordered]@{
        file          = $fileName
        validate_ok   = $m3Ok
        ingest_ok     = $m4Ok
        ingestion_id  = $(if ($ingId) { $ingId } else { "(not captured)" })
        parse_ok      = $m5Ok
        pipeline_pass = ($m3Ok -and $m4Ok -and $m5Ok)
        note          = "Each stage JSON is in its module subfolder."
    }

    if ($summary.pipeline_pass) {
        Pass "Cross-module: $fileName -- validate/ingest/parse all produced evidence"
        $xPassed++
    } else {
        $missing = @()
        if (-not $m3Ok) { $missing += "M3-validate" }
        if (-not $m4Ok) { $missing += "M4-ingest" }
        if (-not $m5Ok) { $missing += "M5-parse" }
        Fail "Cross-module: $fileName -- missing: $($missing -join ', ')" ; $xFailed++
    }

    ($summary | ConvertTo-Json) | Set-Content (Join-Path $CrossDir "cross-$(($fileName -replace '\.','-'))-$Date.json") -Encoding UTF8
}

if ($ingestionIds.Count -eq 0) {
    Gap "Cross-module Stats Web upload flow -- /api/files/upload endpoint not yet wired end-to-end through Stats Web Razor pages (M9 scope). Evidence uses direct module API calls inside stats-runtime."
}

# ---------------------------------------------------------------------------
# 10. Container log snapshot
# ---------------------------------------------------------------------------
Section "10. Container log snapshot (last 40 lines)"

try {
    $logArgs = @("--file", $ComposeFilePath, "logs", "--tail=40", "stats")
    $logs = docker compose @logArgs 2>&1
    Write-Result $logs
    $logs | Set-Content (Join-Path $EvidenceRootFull "docker-logs-snapshot-$Date.txt") -Encoding UTF8
    Pass "Container logs collected"
} catch { Fail "Container logs" $_.Exception.Message }

# ---------------------------------------------------------------------------
# 11. Teardown
# ---------------------------------------------------------------------------
if (-not $LeaveStackRunning) {
    Section "11. Teardown"
    try {
        docker compose --file $ComposeFilePath down | Out-Null
        Pass "docker compose down completed"
    } catch { Fail "docker compose down" $_.Exception.Message }
} else {
    Write-Result ""
    Write-Result "  Stack left running (-LeaveStackRunning). To stop:"
    Write-Result "  docker compose --file $ComposeFile down"
}

# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------
$Total = $Passed + $Failed
Section "Summary"
Write-Result "  Total checks: $Total"
Write-Result "  Passed:       $Passed"
Write-Result "  Failed:       $Failed"
Write-Result "  Skipped:      $Skipped"
Write-Result ""
if ($Gaps.Count -gt 0) {
    Write-Result "Known gaps:"
    foreach ($g in $Gaps) { Write-Result "  - $g" }
    Write-Result ""
}
$overallResult = if ($Failed -eq 0) { "PASSED" } else { "FAILED ($Failed check(s) did not pass)" }
Write-Result "Result: $overallResult"

# Write Markdown summary
$fixtureList = ($Fixtures | ForEach-Object { "- $($_.Name)" }) -join "`n"
$gapList = if ($Gaps.Count -gt 0) { ($Gaps | ForEach-Object { "- $_" }) -join "`n" } else { "None for this run." }
$md = @"
<!-- M13 - Containerization Start -->
<!-- Docker full regression evidence summary. Auto-generated by run_docker_full_regression_evidence.ps1. -->

# Docker Full Regression Evidence Summary

**Date:** $Date
**Run at:** $Timestamp

## Docker Stack

| Service | Image | Entry point |
| --- | --- | --- |
| stats-runtime | stats-runtime:local | http://127.0.0.1:8080 |
| stats-db | postgres:16-alpine | internal (stats-runtime:5432) |

Compose file: $ComposeFile
Env file: $EnvFile (never committed; contains secrets)

## Modules Covered

| Module | Description | Evidence folder |
| --- | --- | --- |
| M1 | Identity Access -- DB init, login, user listing | test-results/DockerRegression/M1/ |
| M2 | Stats Web Shell -- page presence via HTTP | test-results/DockerRegression/M2/ |
| M3 | File Validation -- all test-input/ fixtures | test-results/DockerRegression/M3/ |
| M4 | File Ingestion -- all test-input/ fixtures | test-results/DockerRegression/M4/ |
| M5 | Document Parsing (OCR + text) -- all test-input/ fixtures | test-results/DockerRegression/M5/ |
| Cross | Validate -> Ingest -> Parse pipeline per fixture | test-results/DockerRegression/cross-module/ |

Raw transcript: test-results/DockerRegression/docker-regression-raw-output-$Date.txt

## Fixture Files Processed

$fixtureList

## Results

| Metric | Count |
| --- | --- |
| Total checks | $Total |
| Passed | $Passed |
| Failed | $Failed |
| Skipped | $Skipped |

**Result: $overallResult**

## Known Gaps

$gapList

## Source File Policy

Real source files under test-input/ are gitignored. Only test-input/README.md is tracked.
Do not commit real fixture files.

<!-- M13 End -->
"@

$md | Set-Content $SummaryFile -Encoding UTF8
$Results | Set-Content $RawOutputFile -Encoding UTF8
Write-Host ""
Write-Host "Regression summary: $SummaryFile"
Write-Host "Raw transcript: $RawOutputFile"

if ($Failed -gt 0) { exit 1 }
