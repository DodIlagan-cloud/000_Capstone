# M3/M4 - File Validation and Ingestion: Local app-flow evidence script
#
# TESTING BOUNDARY (established in M13):
#   Unit tests:             run on the host with pytest (fast development feedback)
#   Acceptance / evidence:  run in Docker using tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1
#
# This script targets the LOCAL runtime (Stats Web on port 5013, file intake on 8014).
# It is suitable for development-time evidence only. For assessment/capstone evidence,
# use the M13 Docker acceptance script which exercises the full containerized runtime.
#
# PREREQUISITE: Stats Web and the File Validation API must be running locally before executing this script.

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$ConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.json"
$LocalConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.local.json"
$Settings = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $LocalConfigPath) {
    $LocalSettings = Get-Content -Path $LocalConfigPath -Raw | ConvertFrom-Json
    foreach ($section in @("evidenceFolders", "moduleFolders", "scriptFolders", "localPaths", "runtime")) {
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

$EvidenceDir = Resolve-ConfiguredPath $Settings.evidenceFolders.M3M4AppFlow
$TestDataDir = if ($env:STATS_TESTDATA_DIR) { $env:STATS_TESTDATA_DIR } else { $Settings.localPaths.testDataDir }
if (-not $TestDataDir) {
    throw "Set STATS_TESTDATA_DIR or tests\scripts\config\test-script-settings.local.json localPaths.testDataDir before running this evidence script."
}
$PdfPath = Join-Path $TestDataDir $Settings.localPaths.m3M4AppFlowPdfName
$BaseUrl = $Settings.runtime.statsWebBaseUrl
$RemoteDebuggingPort = [int] $Settings.runtime.m3M4EdgeDebugPort
$AdminEmail = "admin.manual@example.com"
$AdminPassword = "EvidenceAdmin123"

New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null

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
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket
    )

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
        throw ($result.exceptionDetails | ConvertTo-Json -Depth 20)
    }

    return $result.result.value
}

function Wait-CdpFor {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket,
        [string] $Expression,
        [int] $TimeoutSeconds = 15
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $ready = Invoke-CdpEval -Socket $Socket -Expression "Boolean($Expression)"
            if ($ready) {
                return
            }
        } catch {
            # The page may still be navigating.
        }

        Start-Sleep -Milliseconds 400
    }

    throw "Timed out waiting for: $Expression"
}

function Set-CdpViewport {
    param(
        [System.Net.WebSockets.ClientWebSocket] $Socket
    )

    Invoke-Cdp -Socket $Socket -Method "Emulation.setDeviceMetricsOverride" -Params @{
        width = 1440
        height = 950
        deviceScaleFactor = 1
        mobile = $false
    } | Out-Null
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

$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$socket.ConnectAsync([Uri](Get-PageWebSocketUrl), [Threading.CancellationToken]::None).GetAwaiter().GetResult()

try {
    Invoke-Cdp -Socket $socket -Method "Page.enable" | Out-Null
    Invoke-Cdp -Socket $socket -Method "Runtime.enable" | Out-Null
    Set-CdpViewport -Socket $socket

    Open-CdpPage -Socket $socket -Url "$BaseUrl/Login"
    Invoke-CdpEval -Socket $socket -Expression "sessionStorage.removeItem('stats.accessToken'); location.assign('/Login')" | Out-Null
    Start-Sleep -Milliseconds 900
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#login-form')"
    Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  document.querySelector('#email').value = '$AdminEmail';
  document.querySelector('#password').value = '$AdminPassword';
  document.querySelector('#login-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
})()
"@ | Out-Null
    Wait-CdpFor -Socket $socket -Expression "location.pathname === '/' && document.querySelector('#app-message')?.textContent.includes('Access granted')" -TimeoutSeconds 20
    $signedInShot = Save-CdpScreenshot -Socket $socket -Name "01-signed-in-home.png"

    Open-CdpPage -Socket $socket -Url "$BaseUrl/Users"
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#create-user-form') && !document.querySelector('#users-workspace').hidden" -TimeoutSeconds 20
    $stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
    $evidenceUser = "evidence.user.$stamp@example.com"
    Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  const form = document.querySelector('#create-user-form');
  form.email.value = '$evidenceUser';
  form.full_name.value = 'Evidence Flow User';
  form.password.value = 'EvidenceUser123';
  form.role.value = 'user';
  form.is_active.checked = true;
  form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
})()
"@ | Out-Null
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#create-message')?.textContent.includes('created')" -TimeoutSeconds 20
    $userShot = Save-CdpScreenshot -Socket $socket -Name "02-user-created.png"

    Open-CdpPage -Socket $socket -Url "$BaseUrl/Upload"
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#document-drop-zone') && !document.querySelector('#landing-workspace').hidden" -TimeoutSeconds 20
    $pdfBase64 = [Convert]::ToBase64String((Get-Content -LiteralPath $PdfPath -Encoding Byte))
    Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  const base64 = '$pdfBase64';
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const file = new File([bytes], '202311_BPICCBE20231108.pdf', { type: 'application/pdf' });
  const dataTransfer = new DataTransfer();
  dataTransfer.items.add(file);
  const dropZone = document.querySelector('#document-drop-zone');
  dropZone.dispatchEvent(new DragEvent('dragenter', { bubbles: true, cancelable: true, dataTransfer }));
  dropZone.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer }));
  dropZone.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer }));
})()
"@ | Out-Null
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#validation-result h3')?.textContent === 'Accepted'" -TimeoutSeconds 25
    $validationShot = Save-CdpScreenshot -Socket $socket -Name "03-real-pdf-dropped-and-validated.png"

    Invoke-CdpEval -Socket $socket -Expression "document.querySelector('#continue-processing-button').click()" | Out-Null
    Wait-CdpFor -Socket $socket -Expression "document.querySelector('#ingestion-result h3')?.textContent.includes('Queued')" -TimeoutSeconds 25
    $ingestionShot = Save-CdpScreenshot -Socket $socket -Name "04-validation-gated-ingestion-result.png"
    $appSummary = Invoke-CdpEval -Socket $socket -Expression @"
(() => {
  const values = [...document.querySelectorAll('#ingestion-result dd')].map(node => node.textContent.trim());
  return {
    ingestion_id: values[0],
    status: values[1],
    submitted_by: values[2],
    processing_file: values[3],
    workflow: values[4],
    state: document.querySelector('#upload-state')?.textContent.trim(),
    selected_file: document.querySelector('#selected-file-summary strong')?.textContent.trim()
  };
})()
"@

    $summary = [ordered]@{
        evidence_user = $evidenceUser
        source_pdf = $PdfPath
        screenshots = @($signedInShot, $userShot, $validationShot, $ingestionShot)
        app_summary = $appSummary
    }
    $summaryPath = Join-Path $EvidenceDir "app-flow-summary.json"
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
