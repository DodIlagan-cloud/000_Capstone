# M14 - Cloud Readiness Start
# Builds the Stats runtime image in Azure Container Registry using ACR Tasks.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9._()-]+$')]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$Location,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-zA-Z0-9]+$')]
    [string]$AcrName,

    [string]$AcrSku = "Basic",

    [string]$ImageName = "stats-runtime",

    [string]$ImageTag = ((Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")),

    [string]$Dockerfile = "infrastructure/containers/stats/Dockerfile",

    [string]$ContextPath = ".",

    [switch]$SkipResourceCreate
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AzureCli {
    $azCommand = Get-Command az -ErrorAction SilentlyContinue
    if ($azCommand) {
        return $azCommand.Source
    }

    $defaultAzPath = "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"
    if (Test-Path -LiteralPath $defaultAzPath) {
        return $defaultAzPath
    }

    throw "Azure CLI was not found on PATH or at $defaultAzPath."
}

function Invoke-AzCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $script:AzCli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
}

$repoRoot = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")
$dockerfilePath = Resolve-Path -LiteralPath (Join-Path $repoRoot $Dockerfile)
$contextRoot = Resolve-Path -LiteralPath (Join-Path $repoRoot $ContextPath)
$script:AzCli = Resolve-AzureCli

Write-Host "[Stats Cloud] Azure CLI: $script:AzCli"
Write-Host "[Stats Cloud] Resource group: $ResourceGroup"
Write-Host "[Stats Cloud] Location: $Location"
Write-Host "[Stats Cloud] Container registry: $AcrName"
Write-Host "[Stats Cloud] Image: ${ImageName}:${ImageTag}"
Write-Host "[Stats Cloud] Dockerfile: $dockerfilePath"
Write-Host "[Stats Cloud] Context: $contextRoot"

Invoke-AzCli @("account", "show", "--query", "{name:name,id:id,user:user.name}", "--output", "table")

if (-not $SkipResourceCreate) {
    if ($PSCmdlet.ShouldProcess($ResourceGroup, "create or update Azure resource group")) {
        Invoke-AzCli @(
            "group", "create",
            "--name", $ResourceGroup,
            "--location", $Location,
            "--output", "table"
        )
    }

    if ($PSCmdlet.ShouldProcess($AcrName, "create Azure Container Registry if missing")) {
        Invoke-AzCli @(
            "acr", "create",
            "--resource-group", $ResourceGroup,
            "--name", $AcrName,
            "--sku", $AcrSku,
            "--admin-enabled", "false",
            "--output", "table"
        )
    }
}

if ($PSCmdlet.ShouldProcess("${AcrName}/${ImageName}:${ImageTag}", "build image in Azure Container Registry")) {
    Push-Location $repoRoot
    try {
        Invoke-AzCli @(
            "acr", "build",
            "--registry", $AcrName,
            "--image", "${ImageName}:${ImageTag}",
            "--file", $Dockerfile,
            $ContextPath
        )
    }
    finally {
        Pop-Location
    }
}

Write-Host "[Stats Cloud] Azure build complete: ${AcrName}.azurecr.io/${ImageName}:${ImageTag}"

# M14 - Cloud Readiness End
