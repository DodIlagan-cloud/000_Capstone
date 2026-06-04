<!-- M14 - Cloud Readiness Start -->
<!-- Practical plan for deploying to Azure and continuing development from the cloud environment. -->

# M14 Azure Development Continuation Plan

## Direction

The Stats cloud development environment should use:

- Azure Container Apps for the containerized Stats runtime.
- Azure Container Registry for the M13 image.
- Azure SQL Database for operational persistence.
- Azure Blob Storage for durable document storage after the storage provider is implemented.
- Microsoft Fabric for curated analytical data and semantic modelling.
- Power BI for dashboard/report authoring and embedding.
- Managed identity and Key Vault-backed secrets wherever possible.

This is a student capstone deployment, so M14 should mimic production concepts without taking on production-scale cost. The practical target is a cost-conscious production simulation: Azure-side image builds, Container Apps deployment mechanics, managed configuration, secret handling, health checks, logs, revision evidence, and CI/CD gates, using the smallest practical resource choices. See `docs/M14-student-production-ci-cd-plan.md`.

## Cloud-Dev Role

`cloud-dev` is the Azure environment where development continues for the remaining app components.

The local machine remains the fastest coding and unit-test loop, but `cloud-dev` becomes the shared cloud runtime for checking how the integrated app behaves in Azure.

The intended development loop is:

1. Implement or update a component locally.
2. Run focused local tests.
3. Build and push a new `stats-runtime` image to Azure Container Registry.
4. Deploy the image to the `cloud-dev` Container App.
5. Run `/health` and component-specific cloud smoke tests.
6. Inspect cloud logs and capture evidence when needed.
7. Keep `prod-sim` for later production-style deployment practice.

## Current Gap

The current M13 runtime is ready for container-first deployment, but the application is not yet fully Azure SQL-native.

Known gaps before Azure can become the main development environment:

- Some module persistence is still PostgreSQL-oriented through local/container `DATABASE_URL`.
- M9 must define the Azure SQL schema, migrations, and data access boundary.
- Storage is still `LocalFileSystem` until an `AzureBlobStorage` provider is implemented.
- Fabric and Power BI are configured as M14/M11 targets, but reports, semantic models, and embed endpoints are not implemented yet.

## Phase 1: Cloud-Dev Landing Environment

Create the Azure resources needed to continue development in `cloud-dev`:

1. Resource group.
2. Azure Container Registry.
3. Azure Container Apps environment.
4. Stats Container App.
5. Azure SQL logical server and database.
6. Key Vault.
7. Managed identity.
8. Storage account and Blob container.
9. Fabric workspace, later when reporting development needs it.
10. Power BI workspace, later when reporting development needs it.

Evidence to capture:

- Resource names with subscription IDs redacted if required.
- Managed identity assignments.
- Key Vault secret names only, not values.
- Public Stats Web `/health` result.

## Phase 2: Deploy Cloud-Dev Runtime

Deploy the current container to Azure Container Apps:

1. Build the `stats-runtime` image.
2. Push to Azure Container Registry.
3. Configure Container Apps environment variables from `infrastructure/cloud/azure-container-apps.env.example`.
4. Configure secrets from Key Vault or Container Apps secrets.
5. Configure health probe against `/health`.
6. Confirm logs flow to Azure monitoring.

This phase proves hosting works and establishes the development deployment loop, but does not yet make Azure SQL the complete operational store.

## Phase 3: M9 Azure SQL Persistence

Move operational persistence behind an Azure SQL-compatible boundary:

1. Define Stats tables for users, documents, ingestion records, parse results, extraction results, validation results, and reporting snapshots.
2. Add migrations owned by M9.
3. Update persistence adapters to use Azure SQL-compatible drivers and connection configuration.
4. Prefer managed identity authentication for cloud.
5. Keep local/container Compose support for development diagnostics.
6. Add integration tests for Azure SQL connection configuration without committing credentials.

Acceptance target:

- Azure Container Apps runtime can read/write operational Stats records to Azure SQL.

## Phase 4: Blob Storage

Implement durable document storage:

1. Add `AzureBlobStorage` provider behind `STATS_STORAGE_PROVIDER`.
2. Store accepted documents and redacted evidence artefacts in configured containers.
3. Use managed identity for Blob access where possible.
4. Keep local filesystem as the local diagnostic provider.

Acceptance target:

- Uploaded files survive container revision replacement.

## Phase 5: Fabric and Power BI

Connect reporting to the cloud data model:

1. Publish approved Azure SQL reporting views or snapshots.
2. Ingest or mirror reporting data into Fabric.
3. Build Fabric lakehouse, warehouse, or semantic model.
4. Author Power BI reports over the curated model.
5. Configure either secure portal links or server-side embedded analytics.
6. Add Stats Web configuration for workspace/report IDs.

Acceptance target:

- Stats Web can show or link to the Power BI dashboard without exposing embed tokens or service principal secrets in browser JavaScript.

## Phase 6: Continue Development From Azure Through Cloud-Dev

After the `cloud-dev` Container App is running, use Azure as the shared development runtime:

- Developers build and test locally through Docker for fast iteration.
- Development builds deploy to the `cloud-dev` Container App.
- Azure SQL stores shared development data after M9 is ready.
- Fabric/Power BI hosts reporting work after M11 reporting development reaches that point.
- Regression evidence includes local container checks and cloud health/reporting checks.

Do not make Azure the only development path until local Docker and cloud deployment both pass the same core contract tests.

<!-- M14 - Cloud Readiness End -->
