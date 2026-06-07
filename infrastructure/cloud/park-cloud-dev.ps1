# M14 - Cloud Readiness Start
# Parks cloud-dev without deleting resources by scaling the Stats Container App to zero minimum replicas.

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ResourceGroup = "rg-stats-dev",
    [string]$ContainerAppName = "ca-stats-dev-001",
    [int]$MinReplicas = 0,
    [int]$MaxReplicas = 1
)

$ErrorActionPreference = "Stop"

if ($MinReplicas -lt 0) {
    throw "MinReplicas cannot be less than zero."
}

if ($MaxReplicas -lt 1) {
    throw "MaxReplicas must be at least one so cloud-dev can wake for tests."
}

if ($MinReplicas -gt $MaxReplicas) {
    throw "MinReplicas cannot be greater than MaxReplicas."
}

Write-Output "Parking cloud-dev Container App '$ContainerAppName'."
Write-Output "No resources will be deleted."
Write-Output "Target scale: min=$MinReplicas max=$MaxReplicas"

if ($PSCmdlet.ShouldProcess($ContainerAppName, "Scale Container App to min=$MinReplicas max=$MaxReplicas")) {
    & az containerapp update `
        --name $ContainerAppName `
        --resource-group $ResourceGroup `
        --min-replicas $MinReplicas `
        --max-replicas $MaxReplicas `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to park Container App '$ContainerAppName'."
    }
}

$status = & az containerapp show `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --query "{name:name,image:properties.template.containers[0].image,minReplicas:properties.template.scale.minReplicas,maxReplicas:properties.template.scale.maxReplicas,runningStatus:properties.runningStatus,fqdn:properties.configuration.ingress.fqdn}" `
    --output json

$status

Write-Output "cloud-dev is parked. The URL may cold-start slowly when next used."

# M14 - Cloud Readiness End
