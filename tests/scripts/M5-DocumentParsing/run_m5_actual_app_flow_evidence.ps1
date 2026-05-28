# M5 - Document Parsing Module: Local app-flow evidence script
#
# TESTING BOUNDARY (established in M13):
#   Unit tests:             run on the host with pytest (fast development feedback)
#   Acceptance / evidence:  run in Docker using tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1
#
# This script targets the LOCAL runtime (Stats Web on port 5013, modules on 8013/8014/8015).
# It is suitable for development-time evidence only. For assessment/capstone evidence,
# use the M13 Docker acceptance script which exercises the full containerized runtime.
#
# PREREQUISITE: All module APIs and Stats Web must be running locally before executing this script.

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$ConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.json"
$LocalConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.local.json"
$Settings = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $LocalConfigPath) {
    $LocalSettings = Get-Content -Path $LocalConfigPath -Raw | ConvertFrom-Json
    foreach ($section in @("evidenceFolders", "localPaths", "runtime")) {
        if ($LocalSettings.PSObject.Properties.Name -contains $section) {
            foreach ($property in $LocalSettings.$section.PSObject.Properties) {
                $Settings.$section | Add-Member -NotePropertyName $property.Name -NotePropertyValue $property.Value -Force
            }
        }
    }
}
function Resolve-ConfiguredPath {
    param([string] $PathValue)
    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }
    return Join-Path $RepoRoot $PathValue
}

$EvidenceDir = Resolve-ConfiguredPath $Settings.evidenceFolders.M5DocumentParsing
$TestDataDir = if ($env:STATS_TESTDATA_DIR) { $env:STATS_TESTDATA_DIR } else { $Settings.localPaths.testDataDir }
if (-not $TestDataDir) {
    throw "Set STATS_TESTDATA_DIR or tests\scripts\config\test-script-settings.local.json localPaths.testDataDir before running this evidence script."
}
$PdfPath = Join-Path $TestDataDir $Settings.localPaths.m5AppFlowPdfName
$UploadPdfName = Split-Path -Path $PdfPath -Leaf
$UploadPdfPath = $PdfPath
$BaseUrl = $Settings.runtime.statsWebBaseUrl
$RemoteDebuggingPort = [int] $Settings.runtime.m5EdgeDebugPort
$AdminEmail = "admin.manual@example.com"
$AdminPassword = "EvidenceAdmin123"
$EdgePath = $Settings.localPaths.edgeExecutable
$EvidenceDate = Get-Date -Format "yyyy-MM-dd"

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

function Start-EvidenceEdge {
    $existing = Get-Process msedge -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*--remote-debugging-port=$RemoteDebuggingPort*" } |
        Select-Object -First 1
    if ($existing) {
        return
    }

    Start-Process -FilePath $EdgePath -ArgumentList @(
        "--remote-debugging-port=$RemoteDebuggingPort",
        "--user-data-dir=$EvidenceDir\edge-profile",
        "--window-size=1440,950",
        "--window-position=40,40",
        "$BaseUrl/Login"
    ) | Out-Null
    Start-Sleep -Seconds 3
}

function Get-PageWebSocketUrl {
    $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$RemoteDebuggingPort/json/list"
    $page = $targets |
        Where-Object { $_.type -eq "page" -and $_.url -like "$BaseUrl*" } |
        Select-Object -First 1
    if (-not $page) {
        $page = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
    }
    if (-not $page) {
        throw "No Edge page target found on the remote debugging port."
    }

    return $page.webSocketDebuggerUrl
}

function Receive-CdpMessage {
    param([System.Net.WebSockets.ClientWebSocket] $Socket)

    $buffer = New-Object byte[] 1048576
    $builder = [System.Text.StringBuilder]::new()
    do {
        $segment = [ArraySegment[byte]]::new($buffer)
        $result = $Socket.ReceiveAsync($segment, [Threading.CancellationToken]::None).GetAwaiter().GetResult()
        if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
            throw "CDP WebSocket closed unexpectedly."
        }

        $chunk = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count)
        [void] $builder.Append($chunk)
    } until ($result.EndOfMessage)

    return $builder.ToString() | ConvertFrom-Json
}

$script:CdpId = 0
function Invoke-Cdp {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Method,
        [hashtable] $Params = @{}
    )

    $script:CdpId += 1
    $message = @{
        id = $script:CdpId
        method = $Method
        params = $Params
    } | ConvertTo-Json -Depth 30 -Compress

    $bytes = [System.Text.Encoding]::UTF8.GetBytes($message)
    $Socket.SendAsync(
        [ArraySegment[byte]]::new($bytes),
        [System.Net.WebSockets.WebSocketMessageType]::Text,
        $true,
        [Threading.CancellationToken]::None
    ).GetAwaiter().GetResult()

    while ($true) {
        $response = Receive-CdpMessage -Socket $Socket
        if ($response.id -eq $script:CdpId) {
            if ($response.error) {
                throw ($response.error | ConvertTo-Json -Depth 10)
            }

            return $response.result
        }
    }
}

function Invoke-CdpEval {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Expression
    )

    $result = Invoke-Cdp -Socket $Socket -Method "Runtime.evaluate" -Params @{
        expression = $Expression
        awaitPromise = $true
        returnByValue = $true
    }

    if ($result.exceptionDetails) {
        Write-Host "CDP expression failed:"
        Write-Host $Expression
        throw ($result.exceptionDetails | ConvertTo-Json -Depth 20)
    }

    return $result.result.value
}

function Wait-CdpFor {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Expression,
        [int] $TimeoutSeconds = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $ready = Invoke-CdpEval -Socket $Socket -Expression "Boolean($Expression)"
            if ($ready) {
                return
            }
        } catch {
        }

        Start-Sleep -Milliseconds 400
    }

    throw "Timed out waiting for: $Expression"
}

function Open-CdpPage {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Url
    )

    Invoke-Cdp -Socket $Socket -Method "Page.navigate" -Params @{ url = $Url } | Out-Null
    Start-Sleep -Milliseconds 1400
}

function Save-CdpScreenshot {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Name
    )

    Start-Sleep -Milliseconds 500
    $screenshot = Invoke-Cdp -Socket $Socket -Method "Page.captureScreenshot" -Params @{
        format = "png"
        captureBeyondViewport = $true
    }
    $target = Join-Path $EvidenceDir $Name
    [IO.File]::WriteAllBytes($target, [Convert]::FromBase64String($screenshot.data))
    return $target
}

Start-EvidenceEdge
if (-not (Test-Path -LiteralPath $UploadPdfPath)) {
    throw "Approved TestData file was not found: $UploadPdfPath"
}

$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$socket.ConnectAsync([Uri](Get-PageWebSocketUrl), [Threading.CancellationToken]::None).GetAwaiter().GetResult()

try {
    Invoke-Cdp -Socket $socket -Method "Page.enable" | Out-Null
    Invoke-Cdp -Socket $socket -Method "Runtime.enable" | Out-Null
    Invoke-Cdp -Socket $socket -Method "Emulation.setDeviceMetricsOverride" -Params @{
        width = 1440
        height = 950
        deviceScaleFactor = 1
        mobile = $false
    } | Out-Null

    Open-CdpPage -Socket $socket -Url "$BaseUrl/Login"
    Invoke-CdpEval -Socket $socket -Expression "(() => { sessionStorage.removeItem('stats.accessToken'); location.assign('/Login'); return true; })()" | Out-Null
    Start-Sleep -Milliseconds 900
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#login-form')"
    Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  document.querySelector('#email').value = '$AdminEmail';
  document.querySelector('#password').value = '$AdminPassword';
  document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
})()
"@ | Out-Null
    Wait-CdpFor -Socket $socket -Expression "location.pathname === '/' && document.querySelector('#app-message') && document.querySelector('#app-message').textContent.includes('Access granted')" -TimeoutSeconds 20
    $signedInShot = Save-CdpScreenshot -Socket $socket -Name "M5-DocumentParsing-actual-app-01-signed-in-home-$EvidenceDate.png"

    Open-CdpPage -Socket $socket -Url "$BaseUrl/Upload"
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#document-drop-zone') && !document.querySelector('#landing-workspace').hidden" -TimeoutSeconds 20
    $readyShot = Save-CdpScreenshot -Socket $socket -Name "M5-DocumentParsing-actual-app-02-upload-ready-$EvidenceDate.png"

    $pdfBase64 = [Convert]::ToBase64String((Get-Content -LiteralPath $UploadPdfPath -Encoding Byte))
    Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  const base64 = '$pdfBase64';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const file = new File([bytes], '$UploadPdfName', { type: 'application/pdf' });
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  const dropZone = document.querySelector('#document-drop-zone');
  dropZone.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer }));
  dropZone.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer }));
  dropZone.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer }));
})()
"@ | Out-Null
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#validation-result h3') && document.querySelector('#validation-result h3').textContent === 'Accepted'" -TimeoutSeconds 25
    $validationShot = Save-CdpScreenshot -Socket $socket -Name "M5-DocumentParsing-actual-app-03-validated-$EvidenceDate.png"
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#ingestion-result h3')" -TimeoutSeconds 25
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#parse-result h3') && document.querySelector('#parse-result h3').textContent === 'Parsed'" -TimeoutSeconds 25
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#upload-state') && document.querySelector('#upload-state').textContent.includes('validated and parsed')" -TimeoutSeconds 25
    $parsedShot = Save-CdpScreenshot -Socket $socket -Name "M5-DocumentParsing-actual-app-04-validated-ingested-parsed-$EvidenceDate.png"

    $appSummary = Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  const sectionValues = (selector) => [...document.querySelectorAll(selector + ' dd')].map(node => node.textContent.trim());
  const validation = sectionValues('#validation-result');
  const ingestion = sectionValues('#ingestion-result');
  const parse = sectionValues('#parse-result');
  return {
    upload_state: document.querySelector('#upload-state') ? document.querySelector('#upload-state').textContent.trim() : '',
    selected_file: document.querySelector('#selected-file-summary strong') ? document.querySelector('#selected-file-summary strong').textContent.trim() : '',
    validation: {
      detected_type: validation[0],
      size: validation[1],
      extension: validation[2]
    },
    ingestion: {
      ingestion_id: ingestion[0],
      status: ingestion[1],
      submitted_by: ingestion[2],
      processing_file: ingestion[3],
      workflow: ingestion[4]
    },
    parsing: {
      status: parse[0],
      document_type: parse[1],
      confidence: parse[2],
      strategy: parse[3],
      text_length: parse[4],
      json_visible: Boolean(document.querySelector('#parse-result .json-output pre')),
      json_preview: document.querySelector('#parse-result .json-output pre')
        ? document.querySelector('#parse-result .json-output pre').textContent.slice(0, 240)
        : ''
    }
  };
})()
"@

    $summary = [ordered]@{
        source_pdf = $UploadPdfPath
        screenshots = @($signedInShot, $readyShot, $validationShot, $parsedShot)
        app_summary = $appSummary
    }
    $summaryPath = Join-Path $EvidenceDir "M5-DocumentParsing-actual-app-flow-summary-$EvidenceDate.json"
    $summary | ConvertTo-Json -Depth 10 | Set-Content -Path $summaryPath -Encoding UTF8
    $summary | ConvertTo-Json -Depth 10
} finally {
    if ($socket.State -eq [System.Net.WebSockets.WebSocketState]::Open) {
        $socket.CloseAsync(
            [System.Net.WebSockets.WebSocketCloseStatus]::NormalClosure,
            "done",
            [Threading.CancellationToken]::None
        ).GetAwaiter().GetResult()
    }
    $socket.Dispose()
}
