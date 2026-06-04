<!-- M14 - Cloud Readiness Start -->
<!-- Azure cloud deployment notes for the Stats runtime. -->

# Stats Cloud Readiness

This folder owns the M14 cloud deployment contract for the Stats project.

The initial target is Azure Container Apps running the M13 `stats-runtime` image from Azure Container Registry, with secrets supplied by Azure Key Vault or Container Apps secrets and runtime logs collected from stdout/stderr.

The cloud data direction is Azure SQL Database for operational persistence, Microsoft Fabric for analytics modelling, and Power BI for report/dashboard delivery. The PostgreSQL `stats-db` service remains local Docker Compose wiring only.

## Target Architecture

| Concern | Target |
| --- | --- |
| Runtime | Azure Container Apps |
| Image registry | Azure Container Registry |
| Database | Azure SQL Database |
| Secrets | Azure Key Vault references or Container Apps secrets |
| Identity | Managed identity for registry, Key Vault, and future storage access |
| Durable files | `LocalFileSystem` for MVP; `AzureBlobStorage` after storage adapter implementation |
| Analytics | Microsoft Fabric workspace |
| Reporting | Power BI workspace, reports, and embedding configuration |
| Public ingress | Stats Web only on `STATS_WEB_PORT` |
| Internal services | Module APIs remain container-local behind Stats Web proxy routes |
| Health probe | HTTP `/health` |
| Logs | Container stdout/stderr with redaction enabled |

## Configuration

Use `azure-container-apps.env.example` as the safe checklist of cloud runtime variables. Do not copy real values into Git.

Secret values must come from Key Vault or Container Apps secrets:

- `AZURE_SQL_CONNECTIONSTRING`
- `ACCESS_TOKEN_SECRET_KEY`
- `DEFAULT_ADMIN_PASSWORD`
- `POWERBI_CLIENT_SECRET`
- Storage keys or SAS tokens, if managed identity storage access is not yet implemented
- Registry credentials, if managed identity registry pull is not available

Non-secret values can be supplied as Container Apps environment variables.

## Deployment Steps

1. Build the image from `infrastructure/containers/stats/Dockerfile`.
2. Tag the image for the target Azure Container Registry.
3. Push the image to Azure Container Registry.
4. Create or update the Azure Container Apps environment.
5. Create or update the Stats Container App using the pushed image.
6. Enable managed identity.
7. Grant identity access to Azure Container Registry pull scope, Azure SQL access, storage access, and required Key Vault secrets.
8. Configure non-secret variables from `azure-container-apps.env.example`.
9. Configure secret variables from Key Vault or Container Apps secrets.
10. Configure an HTTP health probe against `/health` on `STATS_WEB_PORT`.
11. Verify the public Stats Web URL, startup logs, OCR health, Azure SQL connectivity, Fabric/Power BI configuration readiness, and redacted logging.

## First Admin Bootstrap

M1 owns the first administrator creation workflow, but cloud runtime startup must not create privileged users on every container restart.

The cloud-dev/prod-sim pattern is a manual one-time bootstrap job:

```powershell
.\infrastructure\cloud\bootstrap-stats-admin-containerapp-job.ps1
```

The default command creates or updates this manual Azure Container Apps Job:

```text
job-stats-admin-bootstrap
```

It does not start the job unless `-StartJob` is provided.

Run this job only against a fresh database with no existing users:

```powershell
.\infrastructure\cloud\bootstrap-stats-admin-containerapp-job.ps1 -StartJob
```

The job runs the M1 script:

```text
python -m app.scripts.create_admin
```

It uses:

- `DEFAULT_ADMIN_EMAIL` as a non-secret job environment variable.
- `DEFAULT_ADMIN_PASSWORD` from the job secret `default-admin-password`.
- Azure SQL connection details from the job secret `azure-sql-connectionstring`.

The default secret sources are Key Vault secret names, not committed values:

```text
stats-azure-sql-connectionstring
stats-default-admin-password
stats-access-token-secret-key
```

If users already exist, M1 refuses the bootstrap because `create_initial_admin()` is only valid before any account exists.

The runtime Container App and the bootstrap job may use the same user-assigned managed identity for image pull and secret access, but they have different responsibilities. The runtime identity starts the app and reads runtime secrets during normal operation. The bootstrap job identity is used only when the operator intentionally runs the one-time admin creation job against a fresh database.

## Azure-Side Image Build

Use `build-stats-acr-image.ps1` when the image build should happen in Azure instead of on the local workstation. The script creates or reuses a resource group and Azure Container Registry, then runs `az acr build` with the repository root as the build context.

Example:

```powershell
.\infrastructure\cloud\build-stats-acr-image.ps1 `
  -ResourceGroup rg-stats-dev `
  -Location australiaeast `
  -AcrName acrstatsdev001 `
  -ImageTag dev
```

Use `-WhatIf` to preview the Azure resource and image build operations, or `-SkipResourceCreate` when the resource group and registry already exist.

The current M13 runtime still has legacy local-database startup wiring. A running Azure Container App should use the M9 Azure SQL persistence migration before Azure SQL-backed workflows are accepted as operational.

## Azure SQL Notes

Azure SQL Database is the M14 cloud operational store.

Preferred access:

- Container App managed identity.
- Microsoft Entra authentication to Azure SQL.
- No SQL username/password in committed files.

Fallback access:

- Store `AZURE_SQL_CONNECTIONSTRING` in Key Vault or Container Apps secrets.
- Rotate SQL credentials before production use.

M9 owns schema, migrations, persistence adapters, and any move from PostgreSQL-oriented local module drivers to Azure SQL-compatible providers.

Cloud-dev can prove runtime reachability before full persistence is complete, but persistent document, transaction, validation, and dashboard evidence is not accepted until the M9 Azure SQL schema and migration path have been applied to the target database.

## Cloud-Dev Evidence Examples

Practical M14 cloud-dev evidence should include, when the deployed feature is available:

- Stats Web `/health`, `/Login`, and `/Upload` checks against the live Container App URL.
- Upload of approved files from the local `tests/input` fixture set through the cloud-dev Stats Web surface.
- Redacted parse/extraction/validation summaries, including fixture filename, status, document type, extraction method, candidate counts, warnings, and processing time.
- Azure Container App revision status and a redacted stdout/stderr log sample.
- Azure SQL migration or connectivity evidence that records secret names and status only, not secret values.

## Fabric and Power BI Notes

Fabric and Power BI are the analytics/reporting layer.

The expected flow is:

1. Stats operational data is stored in Azure SQL.
2. Approved reporting tables/views are exposed to Fabric by pipeline, dataflow, mirrored data, or another documented integration.
3. Fabric hosts the curated model in a workspace, lakehouse, warehouse, or semantic model.
4. Power BI reports are authored against the curated model.
5. Stats Web either links to secure Power BI reports for internal users or embeds reports through a server-side embed-token flow.

Do not place Power BI service principal secrets, embed tokens, workspace secrets, dataset credentials, or report access tokens in browser JavaScript.

## Health Checks

The cloud deployment must keep the M13 health chain intact:

- Container Apps probe checks Stats Web `/health`.
- `start-stats-runtime.sh` verifies the configured operational database before accepting traffic. The current M13 local runtime still has transitional local database checks until M9 migrates persistence to Azure SQL.
- `start-stats-runtime.sh` starts each module API and waits for its `/health`.
- Document Parsing health must confirm OCR availability when OCR evidence is required.
- Stats Web remains the only public HTTP entry point.

## Monitoring

Application logs must be emitted to stdout/stderr using the project logging registry:

- `LOG_FORMAT=json`
- `LOG_REDACT_SENSITIVE_VALUES=true`
- `LOG_INCLUDE_CORRELATION_ID=true`
- `LOG_DESTINATION=stdout`

Evidence should include a redacted cloud log sample and the active Container App revision status.

## Storage Notes

The MVP can run with `STATS_STORAGE_PROVIDER=LocalFileSystem` for non-durable cloud trials only. Durable cloud document retention requires an `AzureBlobStorage` provider implemented by the storage-owning module before production acceptance.

When Blob Storage is enabled, document these values in cloud configuration:

- `AZURE_STORAGE_ACCOUNT_NAME`
- `AZURE_STORAGE_CONTAINER_NAME`
- `AZURE_CLIENT_ID` when a user-assigned managed identity is required

## Secret Rotation

Before production use, rotate:

- JWT signing secret
- Azure SQL password or database credential secret, if passwordless managed-identity access is not active
- Bootstrap admin temporary password
- Power BI service principal secret, if used
- Any temporary registry or storage credentials

Record the rotation date in deployment evidence without recording the secret value.

## Live Evidence

Live M14 evidence is pending until Azure subscription, budget, and credential approval are available.

Required evidence:

- Image build and push output with secrets redacted.
- Container App revision details.
- Public `/health` response.
- Startup logs showing module health checks passed.
- Database connectivity check.
- Fabric workspace/configuration check.
- Power BI workspace/report configuration check.
- OCR health output.
- Secret source checklist.
- Redacted monitoring/log sample.

<!-- M14 - Cloud Readiness End -->
