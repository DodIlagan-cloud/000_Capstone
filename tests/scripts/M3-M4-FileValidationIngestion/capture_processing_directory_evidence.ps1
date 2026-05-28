$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$ConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.json"
$LocalConfigPath = Join-Path $RepoRoot "tests\scripts\config\test-script-settings.local.json"
$Settings = Get-Content -Path $ConfigPath -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $LocalConfigPath) {
    $LocalSettings = Get-Content -Path $LocalConfigPath -Raw | ConvertFrom-Json
    foreach ($section in @("evidenceFolders", "runtime")) {
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
$BaseUrl = $Settings.runtime.statsWebBaseUrl
$RemoteDebuggingPort = [int] $Settings.runtime.m3M4EdgeDebugPort
$Summary = Get-Content (Join-Path $EvidenceDir "app-flow-summary.json") | ConvertFrom-Json
$ProcessingFile = $Summary.app_summary.processing_file
$ProcessingDirectory = Split-Path -Parent $ProcessingFile
$DirectoryUrl = ([Uri]$ProcessingDirectory).AbsoluteUri + "/"

function Receive-CdpMessage {
    param([System.Net.WebSockets.ClientWebSocket] $Socket)

    $buffer = New-Object byte[] 1048576
    $builder = [System.Text.StringBuilder]::new()
    do {
        $result = $Socket.ReceiveAsync(
            [ArraySegment[byte]]::new($buffer),
            [Threading.CancellationToken]::None
        ).GetAwaiter().GetResult()
        if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {
            throw "CDP WebSocket closed unexpectedly."
        }

        [void] $builder.Append([System.Text.Encoding]::UTF8.GetString($buffer, 0, $result.Count))
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
    } | ConvertTo-Json -Depth 20 -Compress
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

$targets = Invoke-RestMethod -Uri "http://127.0.0.1:$RemoteDebuggingPort/json/list"
$target = $targets |
    Where-Object { $_.type -eq "page" -and $_.url -like "$BaseUrl*" } |
    Select-Object -First 1
if (-not $target) {
    $target = $targets | Where-Object { $_.type -eq "page" } | Select-Object -First 1
}

$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$socket.ConnectAsync([Uri]$target.webSocketDebuggerUrl, [Threading.CancellationToken]::None).GetAwaiter().GetResult()

try {
    Invoke-Cdp -Socket $socket -Method "Page.enable" | Out-Null
    Invoke-Cdp -Socket $socket -Method "Runtime.enable" | Out-Null
    Invoke-Cdp -Socket $socket -Method "Emulation.setDeviceMetricsOverride" -Params @{
        width = 1440
        height = 950
        deviceScaleFactor = 1
        mobile = $false
    } | Out-Null
    Invoke-Cdp -Socket $socket -Method "Page.navigate" -Params @{ url = $DirectoryUrl } | Out-Null
    Start-Sleep -Seconds 2
    $screenshot = Invoke-Cdp -Socket $socket -Method "Page.captureScreenshot" -Params @{
        format = "png"
        captureBeyondViewport = $true
    }
    $targetPath = Join-Path $EvidenceDir "05-processing-directory-file-url.png"
    [IO.File]::WriteAllBytes($targetPath, [Convert]::FromBase64String($screenshot.data))
    [ordered]@{
        processing_directory = $ProcessingDirectory
        processing_file = $ProcessingFile
        screenshot = $targetPath
    } | ConvertTo-Json -Depth 4
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
