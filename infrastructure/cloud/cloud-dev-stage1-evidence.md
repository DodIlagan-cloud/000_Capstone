<!-- M14 - Cloud Readiness Start -->
<!-- Evidence summary for the first cloud-dev image build and registry push. -->

# Cloud-Dev Stage 1 Evidence

## Summary

Stage 1 completed for `cloud-dev`.

The Azure Container Registry exists and contains the `stats-runtime:dev` and `stats-runtime:dev-m9` images.

This is the first step toward making `cloud-dev` the ongoing Azure development runtime for future app components.

After M9 Azure SQL readiness was completed, the first Azure Container Apps runtime was also created for cloud-dev accessibility testing.

## Checks

| Check | Result |
| --- | --- |
| Azure account check | `Azure subscription 1`, signed in as `ejpilagan@gmail.com` |
| M14 cloud-readiness contract | `10 passed` |
| M13 containerization and orchestration contracts | `71 passed` |
| ACR name availability | `acrstatsdev001` was available before creation |

## Resources Created

| Resource | Value |
| --- | --- |
| Resource group | `rg-stats-dev` |
| Region | `australiaeast` |
| Azure Container Registry | `acrstatsdev001` |
| Login server | `acrstatsdev001.azurecr.io` |
| SKU | `Basic` |
| Admin user | `False` |
| Provisioning state | `Succeeded` |

## Image

| Field | Value |
| --- | --- |
| Repository | `stats-runtime` |
| Tags | `dev`, `dev-m9` |
| Active cloud-dev image reference | `acrstatsdev001.azurecr.io/stats-runtime:dev-m9` |
| Active cloud-dev digest | `sha256:b65f90b255eafce7af8f1dfdac138c203769c21c9b58c9744b9560ef87c9d046` |

## Build Notes

The intended `az acr build` path uploaded the clean source context, but the Azure subscription rejected ACR Tasks with:

```text
TasksOperationsNotAllowed
```

For the fast `cloud-dev` lane, the fallback path was used:

1. Build the image locally with Docker Desktop.
2. Authenticate to ACR with Azure CLI.
3. Push `acrstatsdev001.azurecr.io/stats-runtime:dev` to ACR.
4. Verify the `dev` tag exists in ACR.

This keeps `cloud-dev` moving while reserving the production-style CI/CD learning path for `prod-sim`.

The later M9 cloud runtime image also used the local Docker build and push path because the subscription rejected ACR Tasks:

```text
acrstatsdev001.azurecr.io/stats-runtime:dev-m9
```

## First Cloud Runtime

The first `cloud-dev` Azure Container Apps runtime was created after the M9 Azure SQL migration was verified.

| Resource | Value |
| --- | --- |
| Container Apps environment | `cae-stats-dev-001` |
| Container App | `ca-stats-dev-001` |
| Image | `acrstatsdev001.azurecr.io/stats-runtime:dev-m9` |
| Admin bootstrap job | `job-stats-admin-bootstrap` |
| Admin bootstrap image | `acrstatsdev001.azurecr.io/stats-runtime:dev-m9-bootstrap` |
| ACR pull identity | `id-stats-dev-acr-pull` |
| Public URL | `https://ca-stats-dev-001.nicesmoke-3c1ba719.australiaeast.azurecontainerapps.io` |
| Ingress | External |
| Target port | `8080` |
| Runtime database | `sqldb-stats-dev` through `AZURE_SQL_CONNECTIONSTRING` secret |
| Storage mode | `LocalFileSystem` for first cloud-dev test only |

Public endpoint checks:

```text
/health  200  application/json; charset=utf-8
/Login   200  text/html; charset=utf-8
/Upload  200  text/html; charset=utf-8
```

Startup logs confirmed:

```text
Azure SQL is reachable.
Identity DB init complete.
Identity Access API is healthy.
File Validation API is healthy.
Document Parsing API is healthy.
Transaction Extraction API is healthy.
Data Validation API is healthy.
All module APIs healthy. Starting Stats Web on port 8080.
```

## First Admin Bootstrap

M1 first-admin creation is now formalized as a manual one-time Container Apps Job rather than normal app startup.

| Field | Value |
| --- | --- |
| Script | `infrastructure/cloud/bootstrap-stats-admin-containerapp-job.ps1` |
| Job | `job-stats-admin-bootstrap` |
| Trigger | Manual |
| Command | `/app/run-stats-admin-bootstrap.sh` |
| M1 script invoked by runner | `python -m app.scripts.create_admin` |
| Job execution state | No executions run after job creation in the already-bootstrapped database |

The job should be started only against a fresh database with no users:

```powershell
.\infrastructure\cloud\bootstrap-stats-admin-containerapp-job.ps1 -StartJob
```

The current `cloud-dev` admin was created before the job resource existed, then the job was created for repeatable future fresh-environment bootstrapping.

Key Vault now contains these secret names:

```text
stats-access-token-secret-key
stats-azure-sql-connectionstring
stats-default-admin-password
stats-sql-admin-password
```

## Source Adjustments

Two small source adjustments were needed to support clean packaging:

- `.dockerignore` now excludes the root `.pytest_cache/`, `test-results/`, and `node_modules/`.
- `infrastructure/containers/stats/Dockerfile` no longer copies `.gitignore`, because ACR source packaging excludes `.gitignore` by default and the file is not needed at runtime.

## Remaining Cloud-Dev Hardening

The first runtime is accessible, but these items remain development hardening work:

- replace direct Container App secret values with managed identity and Key Vault references,
- add durable Azure Blob Storage for uploaded files,
- configure persistent ASP.NET Data Protection keys,
- add automated deployment through CI/CD instead of local Docker push,
- create Fabric and Power BI resources when reporting work starts,
- keep `prod-sim` separate for production-style approvals, rollback, and monitoring.

<!-- M14 - Cloud Readiness End -->
