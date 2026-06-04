# M1 - User Access Management Start
# Creates or starts the one-time Azure Container Apps Job that bootstraps the first Stats admin.

[CmdletBinding()]
param(
    [string]$ResourceGroup = "rg-stats-dev",
    [string]$EnvironmentName = "cae-stats-dev-001",
    [string]$JobName = "job-stats-admin-bootstrap",
    [string]$Image = "acrstatsdev001.azurecr.io/stats-runtime:dev-m9-bootstrap",
    [string]$RegistryServer = "acrstatsdev001.azurecr.io",
    [string]$RegistryIdentityResourceId = "/subscriptions/a9393569-82cd-48d5-8603-950471fea37a/resourcegroups/rg-stats-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-stats-dev-acr-pull",
    [string]$KeyVaultName = "kv-stats-dev-001",
    [string]$SqlConnectionSecretName = "stats-azure-sql-connectionstring",
    [string]$AdminPasswordSecretName = "stats-default-admin-password",
    [string]$AccessTokenSecretName = "stats-access-token-secret-key",
    [string]$DefaultAdminEmail = "cloud.admin@stats.local",
    [switch]$StartJob
)

$ErrorActionPreference = "Stop"

function New-SecretValue {
    param([int]$ByteCount = 48)

    $bytes = New-Object byte[] $ByteCount
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    [Convert]::ToBase64String($bytes)
}

function Get-KeyVaultSecretValue {
    param(
        [string]$VaultName,
        [string]$SecretName,
        [switch]$CreateIfMissing
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $value = & az keyvault secret show `
        --vault-name $VaultName `
        --name $SecretName `
        --query value `
        --output tsv `
        --only-show-errors 2>$null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference

    if ($exitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($value)) {
        return $value
    }

    if (-not $CreateIfMissing) {
        throw "Missing required Key Vault secret: $SecretName"
    }

    $newValue = New-SecretValue
    & az keyvault secret set `
        --vault-name $VaultName `
        --name $SecretName `
        --value $newValue `
        --output none

    return $newValue
}

$sqlConnectionString = Get-KeyVaultSecretValue `
    -VaultName $KeyVaultName `
    -SecretName $SqlConnectionSecretName

$adminPassword = Get-KeyVaultSecretValue `
    -VaultName $KeyVaultName `
    -SecretName $AdminPasswordSecretName

$accessTokenSecret = Get-KeyVaultSecretValue `
    -VaultName $KeyVaultName `
    -SecretName $AccessTokenSecretName `
    -CreateIfMissing

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
    "DATABASE_PROVIDER=AzureSql",
    "DATABASE_SCHEMA=dbo",
    "AZURE_SQL_CONNECTIONSTRING=secretref:azure-sql-connectionstring",
    "ACCESS_TOKEN_SECRET_KEY=secretref:access-token-secret-key",
    "DEFAULT_ADMIN_EMAIL=$DefaultAdminEmail",
    "DEFAULT_ADMIN_PASSWORD=secretref:default-admin-password"
)

if (-not $jobExists) {
    & az containerapp job create `
        --name $JobName `
        --resource-group $ResourceGroup `
        --environment $EnvironmentName `
        --trigger-type Manual `
        --parallelism 1 `
        --replica-completion-count 1 `
        --replica-retry-limit 0 `
        --replica-timeout 300 `
        --image $Image `
        --registry-server $RegistryServer `
        --registry-identity $RegistryIdentityResourceId `
        --mi-user-assigned $RegistryIdentityResourceId `
        --cpu 0.5 `
        --memory 1.0Gi `
        --secrets `
            "azure-sql-connectionstring=$sqlConnectionString" `
            "default-admin-password=$adminPassword" `
            "access-token-secret-key=$accessTokenSecret" `
        --env-vars $envVars `
        --command /app/run-stats-admin-bootstrap.sh `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create bootstrap job: $JobName"
    }
} else {
    & az containerapp job secret set `
        --name $JobName `
        --resource-group $ResourceGroup `
        --secrets `
            "azure-sql-connectionstring=$sqlConnectionString" `
            "default-admin-password=$adminPassword" `
            "access-token-secret-key=$accessTokenSecret" `
        --output none

    & az containerapp job update `
        --name $JobName `
        --resource-group $ResourceGroup `
        --image $Image `
        --replica-timeout 300 `
        --replica-retry-limit 0 `
        --parallelism 1 `
        --replica-completion-count 1 `
        --cpu 0.5 `
        --memory 1.0Gi `
        --replace-env-vars $envVars `
        --command /app/run-stats-admin-bootstrap.sh `
        --output none
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update bootstrap job: $JobName"
    }
}

Write-Output "Bootstrap job ready: $JobName"
Write-Output "Admin email: $DefaultAdminEmail"
Write-Output "Password source: Key Vault secret '$AdminPasswordSecretName'"

if ($StartJob) {
    Write-Output "Starting bootstrap job. This should only be used against a fresh database with no users."
    & az containerapp job start `
        --name $JobName `
        --resource-group $ResourceGroup `
        --output table
} else {
    Write-Output "Job not started. Run this script with -StartJob only for a fresh database bootstrap."
}

# M1 End
