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
| Durable files | `AzureBlobStorage` for accepted document storage |
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

## Cloud-Dev Parking

Cloud-dev should stay intact while avoiding standing compute cost when the team is not actively testing through the Azure URL.

Parking does not delete resources. It scales the Stats Container App down so the runtime is not kept warm:

```powershell
.\infrastructure\cloud\park-cloud-dev.ps1
```

Default parked scale:

```text
min replicas: 0
max replicas: 1
```

When cloud testing resumes, warm one replica and verify `/health`:

```powershell
.\infrastructure\cloud\resume-cloud-dev.ps1
```

Default active-test scale:

```text
min replicas: 1
max replicas: 1
```

Keep these resources when parked:

- resource group,
- Azure Container Registry,
- Key Vault,
- Azure SQL server and database,
- Container Apps environment,
- Container App definition,
- manual admin bootstrap job,
- managed identities,
- Log Analytics workspace.

Cost-saving behavior while parked:

- Container App compute can scale to zero.
- Azure SQL serverless can auto-pause when idle.
- ACR, Key Vault, identities, and app definitions remain available for the next testing session.

Do not use parking scripts to delete databases, registries, secrets, identities, or deployment history.

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

## M12 Scheduled Email Ingestion Job

M12 owns the unattended mailbox polling trigger. The runtime exposes the
internal-key-protected scheduler endpoint, and cloud-dev/prod-sim uses a scheduled
Azure Container Apps Job to call it:

```text
POST /api/v1/email-ingestions/scheduled-runs
```

Before creating or starting the scheduled job, the always-on Stats Container App
must already be deployed with the M12 runtime settings from
`azure-container-apps.env.example`:

- `EMAIL_PROVIDER=imap`
- `EMAIL_INGESTION_MODE=handoff`
- `EMAIL_SOURCE_CONFIG_STORE=azure_sql`
- `EMAIL_SECRET_PROVIDER=azure_key_vault` or `azure_sql`
- `FILE_INGESTION_BASE_URL=http://localhost:8014`
- `DOCUMENT_PARSING_BASE_URL=http://localhost:8015`
- `TRANSACTION_EXTRACTION_BASE_URL=http://localhost:8016`
- `DATA_VALIDATION_BASE_URL=http://localhost:8017`
- `STATS_DATA_BASE_URL=http://localhost:8018`
- `STATS_INTERNAL_API_KEY`, `AZURE_SQL_CONNECTIONSTRING`, storage settings, and
  `ACCESS_TOKEN_SECRET_KEY` supplied as secret references

Those downstream URLs intentionally stay `localhost`: M12, M3/M4, M5, M7, M8,
M9, and Stats Web run inside the same `stats-runtime` replica, while browsers and
evidence scripts reach M12 only through the public Stats Web ingress.

The job uses the normal `stats-runtime` image with a different command:

```text
/app/run-m12-scheduled-ingestion.sh
```

Create or update the scheduled job:

```powershell
.\infrastructure\cloud\deploy-m12-scheduled-ingestion-containerapp-job.ps1 `
  -StatsWebBaseUrl "https://replace-with-stats-app-hostname.example" `
  -RegistryIdentityResourceId "/subscriptions/<subscription-id>/resourceGroups/rg-stats-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-stats-dev-acr-pull"
```

The default job is:

```text
job-stats-m12-email-ingestion
```

The default schedule is hourly:

```text
0 * * * *
```

For a one-off smoke execution after creation:

```powershell
.\infrastructure\cloud\deploy-m12-scheduled-ingestion-containerapp-job.ps1 `
  -StatsWebBaseUrl "https://replace-with-stats-app-hostname.example" `
  -RegistryIdentityResourceId "/subscriptions/<subscription-id>/resourceGroups/rg-stats-dev/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id-stats-dev-acr-pull" `
  -StartJob
```

The job sends:

- `X-Stats-CSRF: 1`
- `X-Stats-Internal-Key` from the `stats-internal-api-key` Key Vault secret

Overlap controls:

- Container Apps Job is configured with `parallelism=1` and
  `replica-completion-count=1`.
- The M12 scheduler endpoint also has an app-side non-blocking lock, so a second
  tick returns a locked/no-op result if a previous tick is still running in the same
  runtime process.

Do not enable profile cadences for production mailboxes until the manual profile,
saved secrets, PDF password rules, Blob handoff, and database-ingest evidence have
passed.

For cloud M12 acceptance evidence after the manual `Run import` and
`Ingest to database` actions have completed against the public `/EmailSetup`
page, run the suite from the workstation:

```powershell
$env:STATS_INTERNAL_API_KEY = "<internal key value for this evidence session>"
$env:AZURE_SQL_CONNECTIONSTRING = "<Azure SQL connection string or DSN>"
$env:AZURE_STORAGE_ACCOUNT_NAME = "<storage account>"
$env:AZURE_STORAGE_CONTAINER_NAME = "<container>"
python tests\scripts\M12-EmailIngestion\m12_evidence_suite.py --target cloud `
  --web-base-url "https://replace-with-stats-app-hostname.example" `
  --visual-evidence-dir "<folder-with-visual-evidence-manifest>"
```

The cloud suite uses the public Stats Web URL for API proof, local `az` login for
Blob proof, and local `pyodbc` for Azure SQL proof. Do not run the container
target for cloud acceptance evidence; `--target container` proves only the local
`stats-runtime` container.

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

Cloud-dev now uses `STATS_STORAGE_PROVIDER=AzureBlobStorage` for durable accepted-document storage. `LocalFileSystem` remains valid only for isolated local tests and non-cloud debugging.

Blob Storage requires these values in cloud configuration:

- `AZURE_STORAGE_ACCOUNT_NAME`
- `AZURE_STORAGE_CONTAINER_NAME`
- `AZURE_STORAGE_BLOB_PREFIX`
- `AZURE_STORAGE_CONNECTION_STRING` as a Container Apps secret or Key Vault reference until managed identity storage auth is implemented
- `AZURE_CLIENT_ID` when a user-assigned managed identity is required later

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
