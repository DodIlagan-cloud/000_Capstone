<!-- M14 - Cloud Readiness Start -->
<!-- Defines the cloud deployment and environment contract for the Stats runtime. -->

# Module 14 Cloud Readiness Module Specification

## Module Summary

Module 14 establishes the **Cloud Readiness** infrastructure module for the Stats project. It maps the M13 single Stats runtime container to an Azure deployment shape with managed configuration, secrets, storage, monitoring, and documented operational checks.

M14 does not move business logic into infrastructure. It keeps Stats Web, module APIs, OCR, validation, extraction, and persistence ownership in their existing modules, while defining how the built runtime is promoted from local Docker Compose to a cloud-hosted environment.

The preferred initial target is **Azure Container Apps** because the current M13 runtime is already container-first, emits logs to stdout/stderr, exposes `/health`, and can consume environment variables and secret references without source-code edits.

The preferred cloud data and analytics direction is **Azure SQL Database** for operational Stats persistence, **Microsoft Fabric** for curated analytical modelling, and **Power BI** for dashboard/report embedding. Any PostgreSQL references from M13 remain local-container development wiring only and are not the M14 cloud target.

<!-- M14 Recognition Settings Cloud Persistence Start - 2026-06-10 -->
Recognition settings are part of operational Stats persistence. Active document, transaction, and spending classification labels/rules, pending AI/user suggestions, admin approvals, audit records, and synchronization history must live in Azure SQL through M9. They must not be stored as mutable JSON files in the cloud image or in Blob Storage.
<!-- M14 Recognition Settings Cloud Persistence End - 2026-06-10 -->

## Architecture Alignment

M14 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M13-containerization-module-spec.md`
- `docs/privacy-security-data-governance-policy.md`
- `config/stats.runtime.json`
- `config/stats.logging.json`

The building-block plan defines this module as:

| Field | M14 Direction |
| --- | --- |
| Build order | `14` |
| Module | Cloud Readiness |
| Type | Infrastructure |
| Main responsibility | Azure config, secrets, storage, monitoring, deployment notes |
| Reusable output | Deployment and environment contract |

## Goals

- Define the Azure deployment target for the Stats runtime container.
- Document the required cloud configuration variables and which values must come from managed secrets.
- Keep cloud runtime values externalized through environment variables, managed secrets, or configuration files.
- Preserve the M13 container-first runtime contract in cloud: one browser entry point, internal module ports, health checks, and stdout/stderr logs.
- Define cloud storage migration rules so local filesystem intake can later move to Azure Blob Storage behind `STATS_STORAGE_PROVIDER`.
- Define the Azure SQL target and secretless/managed-identity preference for database connectivity.
- Define Azure SQL as the durable home for recognition settings so admin edits and AI/user suggestions survive container rebuilds, revisions, and redeployments.
- Define the Fabric and Power BI boundary for analytics, semantic models, and report embedding.
- Document the minimum monitoring and operational health checks required before a deployment is accepted.
- Provide a cloud environment example without real subscription IDs, credentials, resource names, or secrets.

## Non-Goals

- Running a live Azure deployment from committed scripts.
- Committing Azure credentials, subscription IDs, tenant IDs, database passwords, JWT secrets, or storage account keys.
- Replacing M13 local Docker Compose.
- Implementing Blob Storage adapters or Stats Data migrations. Those belong to the owning storage/persistence modules.
- Implementing CI/CD pipelines. M14 documents the handoff points; a later delivery track may automate them.
- Building Fabric workspaces, lakehouses, warehouses, semantic models, or Power BI reports directly in this repo.
- Multi-region, active-active, or high-availability architecture.
- AKS production architecture.
- Production certification for ISO 27001, SOC 2, PCI DSS, or similar standards.

## Owner Folder

```text
infrastructure/cloud/
```

M14 cloud-readiness assets belong under `infrastructure/cloud/`.

Integration contract tests belong under:

```text
tests/integration/test_m14_cloud_readiness_contract.py
```

## Cloud Deployment Shape

The initial Azure deployment shape is:

| Concern | M14 Target |
| --- | --- |
| Runtime host | Azure Container Apps |
| Container image source | Azure Container Registry |
| Database | Azure SQL Database |
| Secrets | Azure Key Vault references or Container Apps secrets backed by managed identity |
| Durable files | `LocalFileSystem` for current MVP; `AzureBlobStorage` as the cloud migration target |
| Recognition settings | Azure SQL through M9; not runtime JSON and not Blob Storage |
| Analytics | Microsoft Fabric workspace consuming curated Azure SQL exports or mirrored/ingested operational data |
| Reporting | Power BI reports embedded in Stats Web or linked through secure workspace access |
| Logs | Container stdout/stderr collected by Azure monitoring |
| Health | HTTP probe against Stats Web `/health` |
| Ingress | Stats Web only; module API ports remain internal to the container |

The M13 single-container runtime remains valid for the first M14 pass. Splitting modules into separate Container Apps is deferred until there is a product need for independent scaling, deployment, or fault isolation.

## Required Cloud Environment Variables

Committed files may document these names, but real values must be supplied through cloud configuration or managed secrets.

| Variable | Cloud Purpose | Secret |
| --- | --- | --- |
| `STATS_ENVIRONMENT` | Runtime environment label such as `cloud-dev`, `test`, or `prod` | No |
| `STATS_APP_ROOT` | Physical root inside the cloud container, normally `/app` | No |
| `STATS_RUNTIME_CONFIG` | Path to `stats.runtime.json` inside the image | No |
| `STATS_PATHS_CONFIG` | Path to `stats.paths.json` inside the image | No |
| `STATS_LOGGING_CONFIG` | Path to `stats.logging.json` inside the image | No |
| `STATS_STORAGE_PROVIDER` | Storage provider selector; current value `LocalFileSystem`, target value `AzureBlobStorage` | No |
| `AZURE_SQL_CONNECTIONSTRING` | Azure SQL connection string; prefer Microsoft Entra/managed identity authentication | Yes when it contains credentials |
| `ACCESS_TOKEN_SECRET_KEY` | JWT signing secret | Yes |
| `DEFAULT_ADMIN_EMAIL` | Optional bootstrap admin for non-production setup | No |
| `DEFAULT_ADMIN_PASSWORD` | Optional bootstrap admin temporary password | Yes |
| `CORS_ALLOWED_ORIGINS` | Public Stats Web origin allow-list | No |
| `STATS_WEB_PORT` | Container bind port, default `8080` | No |
| `ALLOW_OCR_FALLBACK` | Enables Tesseract OCR in the container | No |
| `OCR_ENGINE` | OCR engine selector, default `tesseract` | No |
| `TESSERACT_CMD` | Tesseract executable path inside the image | No |
| `TESSDATA_PREFIX` | Tesseract language data path inside the image | No |
| `LOG_LEVEL` | Runtime logging level | No |
| `LOG_FORMAT` | Runtime logging format | No |
| `LOG_REDACT_SENSITIVE_VALUES` | Sensitive value redaction switch | No |
| `AZURE_STORAGE_ACCOUNT_NAME` | Storage account name when Blob Storage is enabled | No |
| `AZURE_STORAGE_CONTAINER_NAME` | Blob container name for durable document storage | No |
| `AZURE_CLIENT_ID` | User-assigned managed identity client ID when required by the SDK/runtime | No |
| `FABRIC_WORKSPACE_ID` | Fabric workspace identifier used by deployment/evidence tooling | No |
| `FABRIC_LAKEHOUSE_ID` | Fabric lakehouse or warehouse identifier for curated analytics data | No |
| `POWERBI_WORKSPACE_ID` | Power BI workspace identifier | No |
| `POWERBI_REPORT_ID` | Embedded or linked report identifier | No |
| `POWERBI_TENANT_ID` | Microsoft Entra tenant for Power BI embedding | No |
| `POWERBI_CLIENT_ID` | Service principal client ID when app-owned embedding is used | No |
| `POWERBI_CLIENT_SECRET` | Service principal secret when certificate/managed identity is not yet used | Yes |

## Secrets Boundary

M14 requires all secret values to be managed outside Git:

- `AZURE_SQL_CONNECTIONSTRING` when it contains SQL credentials or access secrets
- `ACCESS_TOKEN_SECRET_KEY`
- `DEFAULT_ADMIN_PASSWORD`
- Storage keys or SAS tokens, if used before managed identity storage access is implemented
- Container registry credentials, if managed identity pull is not available in a target environment
- `POWERBI_CLIENT_SECRET`

The preferred path is managed identity plus Key Vault-backed secret references. If a target environment temporarily uses Container Apps secrets directly, the secret names and ownership must still be documented and rotated before production use.

The runtime Container App and manual bootstrap job may share the same user-assigned managed identity, but they are separate operational paths. Runtime identity is for normal app startup and secret/config access. Bootstrap job identity is for the operator-triggered first-admin creation job only and must not imply that privileged users are recreated on every deployment or restart.

## Storage Boundary

The committed cloud runtime now uses `STATS_STORAGE_PROVIDER=AzureBlobStorage` for accepted document storage. `LocalFileSystem` remains a local-test/debug provider only and must not be accepted as durable cloud document storage.

Cloud acceptance for durable file retention requires `AzureBlobStorage` configuration, secret-backed storage credentials or managed identity access, and evidence that accepted uploads receive `azure-blob://` content references. M14 documents the required cloud variables and acceptance checks; the file-intake module owns the adapter behavior.

Blob Storage is not the persistence layer for active recognition settings. Document files, exported evidence artifacts, or future derived object storage may live in Blob Storage, but approved classification labels/rules and pending suggestions must live in Azure SQL so they can be queried, audited, synchronized, and protected with transactional behavior.

## Database Boundary

The cloud database target is Azure SQL Database.

M14 deployment notes must provide:

- An Azure SQL connection configuration named by environment.
- A managed identity or Microsoft Entra authentication path for the Container App where feasible.
- A fallback Key Vault secret only when passwordless Azure SQL access is not yet available.
- Network access rules or private connectivity notes for the Container Apps environment.
- A migration/init policy owned by M9 Stats Data and Persistence and M1 Identity Access for their tables.
- A clear distinction between local `stats-db` Compose wiring and managed Azure SQL cloud database wiring.

Modules currently using PostgreSQL-specific drivers or SQLAlchemy URLs must be migrated behind a Stats data access boundary before Azure SQL can be the operational store. M14 records the target; M9 owns schema, migrations, and provider-specific persistence changes.

Cloud-dev reachability evidence may be collected before every persistence workflow is complete. However, any evidence claiming durable operational data, restart-safe retrieval, dashboard readiness, or cloud persistence completion depends on M9 applying the Azure SQL schema and migration path to the target database.

Any evidence claiming recognition-setting management is cloud-ready must prove that an admin add/edit/delete or approval writes to Azure SQL and survives a container app revision/redeploy. Rebuilding the image must not be required to preserve or change active labels/rules.

## Fabric and Power BI Boundary

M14 uses Fabric and Power BI as the analytics/reporting layer, not the source of operational truth.

| Concern | Owner | M14 Direction |
| --- | --- | --- |
| Operational records | M9 Stats Data and Persistence | Azure SQL Database |
| Curated analytical model | Fabric | Lakehouse, warehouse, or semantic model fed from approved Stats data |
| Dashboard/report authoring | M11 Stats Dashboard and Reporting plus Power BI workspace | Power BI reports over the curated model |
| Embedded display | Stats Web | Secure portal embedding for internal users or Power BI embedded analytics for app-owned embedding |
| Secrets and identities | M14 infrastructure | Managed identity where available; service principal secret/certificate only when required |

Power BI embedding must not expose workspace secrets, service principal secrets, access tokens, or dataset credentials in browser JavaScript. Stats Web should request embed configuration from a server-side endpoint when embedded analytics is implemented.

## Health and Monitoring

M14 cloud deployment must preserve the M13 health contract:

| Component | Cloud Check |
| --- | --- |
| Stats Web | HTTP health probe against `/health` on `STATS_WEB_PORT` |
| Module APIs | Startup script waits for internal `/health` endpoints before Stats Web starts |
| OCR | Document Parsing `/health` reports OCR availability inside the container |
| Database | Startup verifies the configured operational database before accepting traffic; transitional local database checks remain until M9 migrates persistence to Azure SQL |
| Logs | Application logs go to stdout/stderr with redaction enabled |

Cloud acceptance evidence must include the public Stats Web health response, container revision status, startup log excerpt with module health checks, and one redacted application log sample.

## Deployment Procedure

The M14 manual deployment procedure is:

1. Build the M13 Stats runtime image from `infrastructure/containers/stats/Dockerfile`.
2. Tag the image for the target Azure Container Registry.
3. Push the image to the registry.
4. Create or update the Container Apps environment and Stats Container App.
5. Attach managed identity.
6. Grant identity access to required Key Vault secrets, registry pull scope, Azure SQL access, and storage scope.
7. Configure non-secret environment variables from `infrastructure/cloud/azure-container-apps.env.example`.
8. Configure secret environment variables from Key Vault or Container Apps secrets.
9. Configure an HTTP health probe for `/health`.
10. Verify the public Stats Web URL, module startup logs, OCR health, Azure SQL connectivity, Fabric/Power BI configuration readiness, and redacted logging.

## Testing

M14 contract tests verify:

- The M14 spec exists.
- `infrastructure/cloud/` exists.
- The Azure Container Apps notes exist.
- The cloud environment example exists and does not contain committed secret values.
- Required cloud variables are documented.
- The cloud notes mention Container Apps, Container Registry, Key Vault, managed identity, Azure SQL Database, Fabric, Power BI, Blob Storage, health probes, stdout/stderr logging, and secret rotation.
- `config/stats.runtime.json` names the cloud environment example.

Live deployment evidence is intentionally manual until Azure credentials, subscription ownership, and budget approval are available.

## Evidence

M14 acceptance evidence should include:

- Image build and push output with secrets redacted.
- Container App revision details.
- Public Stats Web `/health` response.
- Startup log showing internal module health checks.
- Database connectivity check.
- Fabric workspace/configuration check.
- Power BI workspace/report configuration check.
- OCR health output.
- Secret source checklist confirming secrets are not committed.
- Monitoring/log screenshot or exported log sample with redaction enabled.

## Acceptance Criteria

M14 is complete when:

- The cloud deployment contract is documented under `docs/` and `infrastructure/cloud/`.
- Required cloud environment variables are listed without real values.
- Secret handling and managed identity expectations are documented.
- Storage, database, monitoring, and health-check boundaries are documented.
- Integration contract tests pass.
- Any live deployment evidence, if produced, is stored under `docs/evidence/` or `tests/results/` with secrets redacted.

<!-- M14 - Cloud Readiness End -->
