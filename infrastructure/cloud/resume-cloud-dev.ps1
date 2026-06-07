# M14 - Cloud Readiness Start
# Resumes cloud-dev for active testing by keeping one Stats Container App replica warm.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ResourceGroup = "rg-stats-dev",
    [string]$ContainerAppName = "ca-stats-dev-001",
    [int]$MinReplicas = 1,
    [int]$MaxReplicas = 1,
    [int]$HealthTimeoutSeconds = 180,
    [switch]$SkipHealthCheck
)

$ErrorActionPreference = "Stop"

if ($MinReplicas -lt 1) {
    throw "Resume should use at least one minimum replica for active cloud testing."
}

if ($MaxReplicas -lt $MinReplicas) {
    throw "MaxReplicas cannot be less than MinReplicas."
}

Write-Output "Resuming cloud-dev Container App '$ContainerAppName'."
Write-Output "Target scale: min=$MinReplicas max=$MaxReplicas"

if ($PSCmdlet.ShouldProcess($ContainerAppName, "Scale Container App to min=$MinReplicas max=$MaxReplicas")) {
    & az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroup `
        --min-replicas $MinReplicas `
        --max-replicas $MaxReplicas `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to resume Container App '$ContainerAppName'."
    }
}

$fqdn = & az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query properties.configuration.ingress.fqdn `
    --output tsv

if ([string]::IsNullOrWhiteSpace($fqdn)) {
    throw "Container App '$ContainerAppName' does not have a public FQDN."
}

$url = "https://$fqdn"
Write-Output "cloud-dev URL: $url"

if (-not $SkipHealthCheck) {
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $healthy = $false

    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri "$url/health" -TimeoutSec 20
            if ($response.status -eq "healthy") {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Seconds 5
        }
    }

    if (-not $healthy) {
        throw "cloud-dev did not return healthy from /health within $HealthTimeoutSeconds seconds."
    }

    Write-Output "cloud-dev /health is healthy."
}

& az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query "{name:name,image:properties.template.containers[0].image,minReplicas:properties.template.scale.minReplicas,maxReplicas:properties.template.scale.maxReplicas,runningStatus:properties.runningStatus,fqdn:properties.configuration.ingress.fqdn}" `
    --output json

# M14 - Cloud Readiness End
