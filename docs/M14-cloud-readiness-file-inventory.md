<!-- M14 - Cloud Readiness Start -->
<!-- Documents the files created or modified for M14 Cloud Readiness. -->

# M14 Cloud Readiness File Inventory

## Summary

This document lists the files created or modified for **M14 Cloud Readiness**. M14 maps the M13 container-first Stats runtime to an Azure cloud deployment contract with Azure SQL, Microsoft Fabric, and Power BI, without committing live cloud credentials, subscription-specific identifiers, or secrets.

Current status: **contract and documentation added**. Live Azure deployment remains pending credential, budget, and environment approval.

## Specification and Documentation

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M14-cloud-readiness-module-spec.md` | Created / Updated | Defines M14 goals, non-goals, Azure Container Apps deployment shape, Azure SQL target, Fabric/Power BI analytics boundary, required cloud variables, secrets boundary, storage/database/monitoring boundaries, deployment procedure, testing, evidence, and acceptance criteria. Updated on 2026-06-10 to define Azure SQL/M9 as the durable home for active recognition settings and to exclude mutable recognition JSON from the cloud image or Blob Storage. |
| `docs/M14-cloud-readiness-file-inventory.md` | Created | This file. Tracks the M14 documentation and contract-test assets. |
| `docs/M14-azure-development-continuation-plan.md` | Created | Practical phased plan for deploying to Azure and continuing development from Azure using Azure SQL, Blob Storage, Fabric, and Power BI. |
| `docs/M14-student-production-ci-cd-plan.md` | Created | Defines the cost-conscious student production simulation, CI/CD learning outcomes, phased Azure resource path, naming convention, cost controls, and approval gates. |
| `docs/cloud-dev-development-rules.md` | Created / Updated | Shared coordination rules and reusable prompt for Codex module agents working against the `cloud-dev` Azure development runtime, including Claude/Copilot review triage expectations. |
| `infrastructure/cloud/M14-azure-build-preview.md` | Created | Human-readable review checklist explaining what the first Azure-side image build will create, why each resource exists, and how the build will run. |
| `infrastructure/cloud/M14-stage0-stage1-execution-checklist.md` | Created | Step-by-step Stage 0 and Stage 1 execution checklist covering local readiness, Azure-side image build commands, evidence capture, and the stop point before Container Apps deployment. |
| `infrastructure/cloud/cloud-dev-stage1-evidence.md` | Created | Records the completed `cloud-dev` Stage 1 resource group, Basic ACR, pushed `stats-runtime:dev` image, ACR Tasks limitation, local Docker fallback, and stop point before Container Apps deployment. |

## Cloud Infrastructure Notes

| File | Change Type | Description |
| --- | --- | --- |
| `infrastructure/cloud/README.md` | Created / Updated | Documents the Azure Container Apps deployment notes, Azure SQL direction, Fabric/Power BI direction, resource responsibilities, configuration mapping, secret handling, health checks, monitoring, deployment steps, and live-evidence expectations. |
| `infrastructure/cloud/azure-container-apps.env.example` | Created / Updated | Safe example of cloud environment variable names, including Azure SQL, Azure Blob Storage, Fabric, Power BI, and recognition-settings service wiring. Uses placeholders only and contains no real secrets. |
| `infrastructure/cloud/build-stats-acr-image.ps1` | Created | Builds the M13 Stats runtime image inside Azure Container Registry with `az acr build` and optional resource group / registry creation. |
| `infrastructure/cloud/bootstrap-stats-admin-containerapp-job.ps1` | Created / Updated | Creates or updates the manual first-admin bootstrap Container Apps Job. Review follow-up replaced the subscription-specific managed identity resource ID default with a placeholder so environment-specific Azure IDs are supplied per deployment instead of committed as defaults. |

## Project Configuration Registry

| File | Change Type | Description |
| --- | --- | --- |
| `config/stats.runtime.json` | Modified | Adds `cloudEnvironmentExample` to the central runtime configuration registry and documents M14 cloud runtime variables. |
| `infrastructure/README.md` | Modified | Updates the infrastructure folder description with the M14 cloud-readiness boundary. |

## Integration Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/integration/test_m14_cloud_readiness_contract.py` | Created / Updated | Verifies the M14 files exist, the cloud example avoids real secrets, required variables are documented, Azure Blob Storage is configured as the durable cloud document-storage target, and cloud deployment notes cover Azure Container Apps, Container Registry, Key Vault, managed identity, Azure SQL, Blob Storage, health probes, stdout/stderr logging, and secret rotation. |

## Verification

Run:

```powershell
pytest tests/integration/test_m14_cloud_readiness_contract.py
```

Expected result:

```text
12 passed
```

<!-- M14 - Cloud Readiness End -->
