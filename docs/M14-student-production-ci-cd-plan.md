<!-- M14 - Cloud Readiness Start -->
<!-- Defines the cost-conscious student production simulation for Azure and CI/CD. -->

# M14 Student Production CI/CD Plan

## Purpose

M14 should teach a production-style Azure delivery model without pretending this student project needs a full enterprise production footprint.

The goal is to build a **cost-conscious production simulation**:

- real Azure services,
- real container image build and deployment flow,
- real environment separation concepts,
- real secret handling,
- real health checks and logs,
- real CI/CD gates,
- intentionally small resource sizes,
- no unnecessary always-on infrastructure.

This plan becomes the practical direction for the new M14 cloud chat.

## Environment Decision

M14 now has two different environment purposes:

| Environment | Purpose | Strategy |
| --- | --- | --- |
| `cloud-dev` | Ongoing Azure development runtime for the rest of the app components | Use scripted execution, smallest practical resources, minimal manual portal work, and only the checks needed to keep feature development moving. |
| `prod-sim` | Learn production-style Azure deployment concepts | Use slower guided execution, Azure Portal inspection, CI/CD gates, approvals, revisions, rollback, monitoring, and evidence. |

All app runtime work should land in **`cloud-dev` first**. Future components should continue to be developed locally, built into the Stats runtime image, deployed to `cloud-dev`, and verified there before any `prod-sim` learning deployment.

`prod-sim` should be planned now, but created later as the teaching environment after `cloud-dev` is usable.

## Cloud-Dev Development Role

`cloud-dev` is the shared development environment for upcoming app components.

It should support:

- fast rebuild and redeploy of the Stats runtime image,
- feature verification for future modules and UI changes,
- development data and test accounts,
- cloud smoke tests after each deployment,
- log inspection for module startup and request flow,
- safe experimentation without production-style approval gates.

`cloud-dev` should not be treated as production. It may use temporary or simplified infrastructure while the project is still evolving, as long as secrets stay out of Git and evidence clearly marks the environment as development.

## Learning Outcomes

By the end of M14, the project should demonstrate that the developer can:

- use `cloud-dev` as the ongoing Azure development runtime,
- later practice production-style deployment in `prod-sim`,
- build and store a container image in Azure Container Registry,
- deploy a containerized app to Azure Container Apps when the database startup path is ready,
- use managed configuration and secrets instead of committed secrets,
- separate local, `cloud-dev`, and later `prod-sim` settings,
- run CI checks before deployment,
- promote a known image tag through a release workflow,
- inspect logs, health probes, revisions, and rollback points,
- explain cost tradeoffs in an Azure architecture.

## Cost-Conscious Production Shape

The M14 target should mimic production concepts while using student-friendly defaults.

| Production Concept | Student-Friendly Implementation |
| --- | --- |
| Container registry | Azure Container Registry Basic SKU |
| Runtime platform | Azure Container Apps Consumption plan |
| Scaling | Minimum replicas set to `0` for idle student/dev use where startup latency is acceptable |
| Deployment unit | Single M13 `stats-runtime` container first |
| Secrets | Container Apps secrets first, Key Vault when the deployment is ready for managed-identity practice |
| Database | Start with documented database boundary; move to Azure SQL after M9 persistence work is ready |
| Storage | Keep `LocalFileSystem` only for non-durable trials; add Blob Storage after provider implementation |
| Observability | Container logs, revision status, `/health`, and redacted log evidence |
| CI/CD | GitHub Actions or Azure DevOps pipeline with build, test, image build, deploy, and evidence steps |
| Governance | Naming convention, tags, budget alert, and manual approval gate before live deploy |

## Recommended Environment Progression

### Stage 0: Local Baseline

Purpose: prove the app works before cloud cost is involved.

Required checks:

- unit tests,
- integration contract tests,
- local container build,
- local Docker Compose health check,
- no committed secrets.

### Stage 1: Cloud-Dev Azure Build Only

Purpose: build the `cloud-dev` image in Azure quickly without running the app yet.

Target environment:

- `cloud-dev`

Azure resources:

- resource group,
- Azure Container Registry,
- ACR build run,
- `stats-runtime` image tag.

No Container App, database, storage, Key Vault, Fabric, or Power BI resources are required at this stage.

### Stage 2: Fast Cloud-Dev Runtime

Purpose: get the app running in Azure Container Apps as quickly as the current runtime allows.

Target environment:

- `cloud-dev`

Azure resources:

- Container Apps environment,
- Stats Container App,
- ingress on Stats Web only,
- health probe on `/health`,
- managed identity where practical,
- Container Apps secrets or Key Vault-backed secrets.

Database note:

The current runtime still performs a PostgreSQL-style startup check. For fastest `cloud-dev`, the next decision is whether to use a temporary reachable PostgreSQL-compatible endpoint for development or pause Stage 2 until the M9 Azure SQL migration is ready.

Once Stage 2 is working, future app components should follow this loop:

1. Build locally.
2. Run focused tests locally.
3. Rebuild and tag the Stats runtime image for `cloud-dev`.
4. Push the image to ACR.
5. Update the `cloud-dev` Container App revision.
6. Run `/health` and focused feature smoke tests.
7. Inspect logs and capture evidence when needed.

### Stage 3: Production Simulation

Purpose: use `prod-sim` to learn the production concepts deliberately.

Target environment:

- `prod-sim`, created only after `cloud-dev` is stable.

Add:

- immutable image tags based on commit SHA or release tag,
- manual deployment approval,
- active revision review,
- rollback to previous revision,
- budget alert,
- secret rotation checklist,
- redacted log evidence,
- `/health` evidence.

`prod-sim` should be built more slowly than `cloud-dev`. It is the place to use the Azure Portal intentionally, compare portal actions with CLI commands, configure CI/CD gates, practice manual approval, and document rollback/evidence.

### Stage 4: Data and Reporting Cloud Stack

Purpose: complete the Azure stack learning path after the operational runtime is stable.

Add when ready:

- Azure SQL Database for M9 persistence,
- Blob Storage after the storage provider exists,
- Fabric workspace for curated analytics,
- Power BI workspace/report for M11 dashboard delivery.

## CI/CD Concept

The production-like pipeline should be simple and explainable.

### Pull Request Checks

Run on every PR:

- install dependencies,
- run Python unit and integration tests,
- run .NET build/tests,
- validate configuration files,
- confirm no obvious secrets are committed,
- optionally build the container without pushing.

### Cloud-Dev Build

Use a fast manual/scripted build while the app is still actively evolving:

- run the minimum local checks,
- build the image locally or in ACR depending on subscription support,
- tag the image as `dev` or with a short timestamp,
- deploy to `cloud-dev` after the runtime startup path is ready,
- smoke test only the changed component plus shared `/health`.

### Prod-Sim Build

Add CI/CD once `prod-sim` is the teaching focus:

- run the same checks,
- build the image in ACR,
- tag the image with the commit SHA,
- record the produced image reference.

### Prod-Sim Manual Deployment

Run only after approval:

- deploy the approved image tag to Azure Container Apps,
- configure environment variables and secret references,
- check `/health`,
- capture revision status and redacted logs.

## Naming Convention

Suggested development names:

| Resource | Name |
| --- | --- |
| Environment label | `cloud-dev` |
| Resource group | `rg-stats-dev` |
| Azure Container Registry | `acrstatsdev001` |
| Container Apps environment | `cae-stats-dev` |
| Container App | `ca-stats-web-dev` |
| Managed identity | `id-stats-dev` |
| Key Vault | `kv-stats-dev-001` |
| Storage account | `ststatsdev001` |
| Azure SQL server | `sql-stats-dev-001` |
| Azure SQL database | `sqldb-stats-dev` |

These names are placeholders until the live Azure build is approved.

Suggested `prod-sim` names:

| Resource | Name |
| --- | --- |
| Environment label | `prod-sim` |
| Resource group | `rg-stats-prod-sim` |
| Container Apps environment | `cae-stats-prod-sim` |
| Container App | `ca-stats-web-prod-sim` |
| Managed identity | `id-stats-prod-sim` |
| Key Vault | `kv-stats-prod-001` |

`prod-sim` may reuse the same ACR to avoid duplicated registry cost, but it should use separate app configuration, secrets, revisions, and evidence.

## Cost Controls

Use these controls before creating live resources:

- create a budget alert for the subscription or Stats resource group,
- use the smallest practical SKUs,
- prefer scale-to-zero for the `cloud-dev` Container App during student/dev use,
- avoid always-on databases until persistence work needs them,
- stop or delete experimental resources after evidence is captured,
- tag all resources with `project=stats`, `workload=cloud-readiness`, `environment=dev`, and `owner=student`,
- do not create Fabric or Power BI resources until the reporting phase needs them.

## Evidence

M14 evidence should prove the learning path, not just the final deployment.

Capture:

- `cloud-dev` build result,
- later `prod-sim` CI check result,
- ACR build result,
- image reference,
- Container App revision details when deployed,
- public `/health` response when deployed,
- redacted logs,
- budget alert or cost-management screenshot,
- secret source checklist,
- rollback notes after revision testing.

## Approval Gate

Before creating resources, confirm:

- target subscription,
- target region,
- budget limit,
- resource names,
- first fast stage to run in `cloud-dev`,
- whether `cloud-dev` should stop at image build or proceed to a running Container App,
- when to start the slower `prod-sim` learning deployment.

<!-- M14 - Cloud Readiness End -->
