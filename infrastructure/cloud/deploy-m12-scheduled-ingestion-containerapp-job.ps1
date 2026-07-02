# M12 - Email Ingestion Module Start
# Creates, updates, or starts the scheduled Azure Container Apps Job for M12 mailbox polling.

[CmdletBinding()]
param(
    [string]$ResourceGroup = "rg-stats-dev",
    [string]$EnvironmentName = "cae-stats-dev-001",
    [string]$JobName = "job-stats-m12-email-ingestion",
    [string]$Image = "acrstatsdev001.azurecr.io/stats-runtime:dev",
    [string]$RegistryServer = "acrstatsdev001.azurecr.io",
    [string]$RegistryIdentityResourceId = "/subscriptions/replace-with-subscription-id/resourcegroups/rg-stats-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-stats-dev-acr-pull",
    [string]$KeyVaultName = "kv-stats-dev-001",
    [string]$InternalApiKeySecretName = "stats-internal-api-key",
    [string]$StatsWebBaseUrl = "https://replace-with-stats-app-hostname.example",
    [string]$CronExpression = "0 * * * *",
    [int]$ReplicaTimeoutSeconds = 3300,
    [switch]$StartJob
)

$ErrorActionPreference = "Stop"

# Resolve the Key Vault secret's URI only (never its value). The job binds the
# secret as a Key Vault reference read by its managed identity, so the secret
# material never passes through the operator session or az CLI arguments.
function Get-KeyVaultSecretUri {
    param(
        [string]$VaultName,
        [string]$SecretName
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $secretUri = & az keyvault secret show `
        --vault-name $VaultName `
        --name $SecretName `
        --query id `
        --output tsv `
        --only-show-errors 2>$null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference

    if ($exitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($secretUri)) {
        return $secretUri
    }

    throw "Missing required Key Vault secret: $SecretName"
}

if ($StatsWebBaseUrl -like "*replace-with*") {
    throw "StatsWebBaseUrl must be the deployed Stats Web base URL before creating the M12 job."
}

if ($RegistryIdentityResourceId -like "*replace-with*") {
    throw "RegistryIdentityResourceId must be the user-assigned managed identity resource id before creating the M12 job."
}

$internalApiKeySecretUri = Get-KeyVaultSecretUri `
    -VaultName $KeyVaultName `
    -SecretName $InternalApiKeySecretName
# Key Vault reference: the job's user-assigned identity fetches the value at
# runtime. The identity needs 'Key Vault Secrets User' (RBAC) or get-secret
# access policy on the vault.
$internalApiKeySecretBinding = "stats-internal-api-key=keyvaultref:$internalApiKeySecretUri,identityref:$RegistryIdentityResourceId"

$jobExists = $false
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& az containerapp job show `
    --name $JobName `
    --resource-group $ResourceGroup `
    --query name `
    --output tsv `
    --only-show-errors 2>$null | Out-Null
$jobShowExitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference

if ($jobShowExitCode -eq 0) {
    $jobExists = $true
}

$envVars = @(
    "STATS_WEB_BASE_URL=$StatsWebBaseUrl",
    "STATS_INTERNAL_API_KEY=secretref:stats-internal-api-key",
    "M12_SCHEDULED_RUN_TIMEOUT_SECONDS=$ReplicaTimeoutSeconds"
)

if (-not $jobExists) {
    & az containerapp job create `
        --name $JobName `
        --resource-group $ResourceGroup `
        --environment $EnvironmentName `
        --trigger-type Schedule `
        --cron-expression $CronExpression `
        --parallelism 1 `
        --replica-completion-count 1 `
        --replica-retry-limit 0 `
        --replica-timeout $ReplicaTimeoutSeconds `
        --image $Image `
        --registry-server $RegistryServer `
        --registry-identity $RegistryIdentityResourceId `
        --mi-user-assigned $RegistryIdentityResourceId `
        --cpu 0.25 `
        --memory 0.5Gi `
        --secrets $internalApiKeySecretBinding `
        --env-vars $envVars `
        --command /app/run-m12-scheduled-ingestion.sh `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create M12 scheduled ingestion job: $JobName"
    }
} else {
    & az containerapp job secret set `
        --name $JobName `
        --resource-group $ResourceGroup `
        --secrets $internalApiKeySecretBinding `
        --output none

    & az containerapp job update `
        --name $JobName `
        --resource-group $ResourceGroup `
        --image $Image `
        --cron-expression $CronExpression `
        --replica-timeout $ReplicaTimeoutSeconds `
        --replica-retry-limit 0 `
        --parallelism 1 `
        --replica-completion-count 1 `
        --cpu 0.25 `
        --memory 0.5Gi `
        --replace-env-vars $envVars `
        --command /app/run-m12-scheduled-ingestion.sh `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update M12 scheduled ingestion job: $JobName"
    }
}

Write-Output "M12 scheduled ingestion job ready: $JobName"
Write-Output "Schedule: $CronExpression"
Write-Output "Stats Web target: $StatsWebBaseUrl"
Write-Output "Internal key source: Key Vault reference '$InternalApiKeySecretName' (resolved by the job's managed identity at runtime)"
Write-Output "Overlap guard: parallelism=1, replica-completion-count=1, timeout=$ReplicaTimeoutSeconds seconds."

if ($StartJob) {
    Write-Output "Starting one manual M12 scheduled-ingestion job execution."
    & az containerapp job start `
        --name $JobName `
        --resource-group $ResourceGroup `
        --output table
} else {
    Write-Output "Job not manually started. Use -StartJob for a one-off smoke execution."
}

# M12 End
