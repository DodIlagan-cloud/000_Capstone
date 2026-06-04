<!-- M14 - Cloud Readiness Start -->
<!-- Execution checklist for local readiness and the first Azure-side image build. -->

# M14 Stage 0 / Stage 1 Execution Checklist

## Purpose

This checklist controls the first live M14 steps.

It covers:

- Stage 0: local readiness checks,
- Stage 1: fast `cloud-dev` Azure-side image build into Azure Container Registry,
- evidence capture,
- explicit stop points before any running cloud app is created.

The budget alert is already set up, so this checklist starts from local verification.

## Confirmed Guardrail

| Item | Status |
| --- | --- |
| Azure budget alert | Completed before resource creation |
| Azure CLI installed | Completed |
| Azure CLI login | Completed |
| ACR name `acrstatsdev001` availability | Checked as available |

## Stage 0: Local Readiness

Stage 0 is intentionally lightweight for `cloud-dev`. Run enough checks to avoid obvious breakage, then move to the Azure build.

### 0.1 Confirm Azure Account

Purpose: make sure commands target the expected subscription.

```powershell
& "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" account show `
  --query "{name:name,id:id,user:user.name,tenantId:tenantId}" `
  --output table
```

Evidence:

- subscription name,
- signed-in user,
- subscription ID redacted if copied into assessment artefacts.

### 0.2 Run M14 Contract Test

Purpose: prove the cloud documentation and configuration contract is coherent.

```powershell
pytest tests\integration\test_m14_cloud_readiness_contract.py
```

Expected:

```text
10 passed
```

Evidence:

- terminal output showing all tests passed.

### 0.3 Run Container-Orchestration Contract Test

Purpose: prove the M13 container contract still exists before using it as the cloud image source.

```powershell
pytest tests\integration\test_stats_web_orchestration_config.py
```

Evidence:

- terminal output showing pass/fail result.

### 0.4 Optional Local Docker Compose Check

Purpose: prove the single runtime still starts locally before building it in Azure.

Only run this if Docker Desktop is available and the local database/runtime check is needed for evidence.

```powershell
docker compose -f infrastructure\compose\stats-runtime.compose.yml up --build
```

In another terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health
```

Evidence:

- Docker startup output,
- `/health` response,
- screenshot if required for module evidence.

Stop the local runtime after evidence is captured.

## Stage 1: Azure-Side Image Build

Stage 1 creates only the minimum resources required to build and store the `cloud-dev` container image in Azure.

### 1.1 Planned Values

| Setting | Value |
| --- | --- |
| Target environment | `cloud-dev` |
| Subscription | `Azure subscription 1` |
| Region | `australiaeast` |
| Resource group | `rg-stats-dev` |
| Azure Container Registry | `acrstatsdev001` |
| ACR SKU | `Basic` |
| Image name | `stats-runtime` |
| First image tag | `dev` |
| Dockerfile | `infrastructure/containers/stats/Dockerfile` |
| Build context | repository root |

### 1.2 Preview Command

Purpose: show what the script intends to do before live execution.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\cloud\build-stats-acr-image.ps1 `
  -ResourceGroup rg-stats-dev `
  -Location australiaeast `
  -AcrName acrstatsdev001 `
  -ImageTag dev `
  -WhatIf
```

Evidence:

- preview output.

Approval point:

- confirm the resource group, region, ACR name, and image tag before continuing.

### 1.3 Live Build Command

Purpose: create/reuse the resource group and ACR, then build the image inside Azure Container Registry.

Run only after the preview is accepted.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\infrastructure\cloud\build-stats-acr-image.ps1 `
  -ResourceGroup rg-stats-dev `
  -Location australiaeast `
  -AcrName acrstatsdev001 `
  -ImageTag dev
```

Expected final image:

```text
acrstatsdev001.azurecr.io/stats-runtime:dev
```

Evidence:

- resource group output,
- ACR output,
- ACR build output,
- final image reference,
- confirmation that no secret values were printed.

### 1.4 Verify Image Exists

Purpose: confirm the image is stored in ACR.

```powershell
& "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" acr repository show-tags `
  --name acrstatsdev001 `
  --repository stats-runtime `
  --output table
```

Evidence:

- `dev` tag appears.

## Stop Point After Stage 1

Stop after the image exists in ACR.

Do not create these yet:

- Azure Container Apps environment,
- Stats Container App,
- Azure SQL,
- Key Vault,
- managed identity,
- Storage account,
- Fabric workspace,
- Power BI workspace.
- any `prod-sim` resource group or app.

Reason:

The current runtime still has a PostgreSQL-style startup dependency. The next design decision is whether Stage 2 uses a temporary database path or waits for the M9 Azure SQL persistence migration.

`prod-sim` waits because it is now the guided production-learning environment, not the fast development lane.

## Stage 1 Acceptance Criteria

Stage 1 is complete when:

- the budget alert is already in place,
- Stage 0 checks have passed or exceptions are documented,
- the resource group exists,
- the ACR exists on Basic SKU,
- the `stats-runtime:dev` image exists in ACR,
- evidence is captured without secrets,
- no running Container App has been created yet,
- no `prod-sim` resources have been created.

<!-- M14 - Cloud Readiness End -->
