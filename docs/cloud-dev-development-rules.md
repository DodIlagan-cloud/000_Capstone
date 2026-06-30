<!-- M14 - Cloud Readiness Start -->
<!-- Shared rules for Codex agents developing against the Stats cloud-dev environment. -->

# Cloud-Dev Development Rules

## Purpose

`cloud-dev` is the shared Azure development runtime for the Stats app.

Each Codex chat working on a module should treat itself as an agent contributing to the same deployable application. Local development still happens first, but any change that affects the integrated runtime must be prepared for `cloud-dev`.

## Current Cloud-Dev Baseline

| Item | Value |
| --- | --- |
| Resource group | `rg-stats-dev` |
| Region | `australiaeast` |
| Azure Container Registry | `acrstatsdev001` |
| Image repository | `stats-runtime` |
| Current live Container App | `ca-stats-dev-001` |
| Current live URL | `https://ca-stats-dev-001.nicesmoke-3c1ba719.australiaeast.azurecontainerapps.io` |
| Current active image pattern | `acrstatsdev001.azurecr.io/stats-runtime:dev-*` |
| Runtime database | Azure SQL Database `sqldb-stats-dev` |
| Current document storage | Azure Blob Storage is the cloud target; durable cloud evidence is still validation pending |

Cloud-dev currently has Azure Container Apps, Azure SQL, Key Vault, ACR, Log Analytics, a manual admin bootstrap job, a user-assigned pull identity, Fabric/Power BI reporting integration, and Azure Blob Storage direction/resources for durable intake. The MVP accepted reporting/Fabric evidence in Wk11, while Blob-backed document/email attachment durability and M12 cloud smoke remain validation pending.

## Agent Rules

### 1. Work Locally First

Agents should implement and test module changes locally before asking for a cloud-dev deployment.

Run focused tests for the changed module and any impacted integration contracts.

### 2. Do Not Create Azure Resources Casually

Agents must not create, delete, or mutate Azure resources unless the user explicitly asks them to do so in that chat.

If Azure resources are needed, the agent should explain:

- what resource is needed,
- why it is needed,
- estimated cost/risk,
- whether it belongs in `cloud-dev` or later `prod-sim`,
- what evidence will be captured.

### 3. Keep Cloud-Dev As The Integration Target

Changes intended for cloud integration should target `cloud-dev` first.

Agents must not deploy directly to `prod-sim`. `prod-sim` is reserved for later production-style learning releases.

### 4. Protect Configuration Boundaries

If a change adds or modifies runtime configuration, update the central config contract:

- `config/stats.runtime.json`,
- `infrastructure/cloud/azure-container-apps.env.example`,
- relevant module spec or file inventory,
- cloud-dev notes when Azure configuration is affected.

Never commit real secrets.

### 5. Treat Database Changes Carefully

Database changes need extra coordination because `cloud-dev` will become the shared development runtime.

M9 or persistence-related agents should document:

- schema change,
- migration/init path,
- seed/dev data expectations,
- local vs cloud-dev database behavior,
- rollback or repair notes.

### 6. Use Traceable Image Tags

Do not rely only on `stats-runtime:dev` once cloud-dev deployments begin.

Preferred tags:

- `dev` for the latest cloud-dev candidate,
- `dev-YYYYMMDD-HHMM` for a rollback checkpoint,
- a short commit or change identifier when available.

### 7. Cloud-Dev Deployment Gate

Before asking to deploy to cloud-dev, the agent should report:

- files changed,
- tests run,
- reviews requested or completed,
- unresolved review findings,
- configuration/env changes,
- database/storage impact,
- whether image rebuild is required,
- proposed image tag,
- smoke tests to run after deployment.

### 8. Cost-Optimized Deployment Rules

Cloud-dev is intentionally low-cost. A new image deployment usually has near-zero incremental Azure cost when the image is built locally, pushed to the existing Basic ACR, and deployed to the existing Consumption-plan Container App. The real costs come from retained image storage, runtime seconds while testing, always-on replicas, and extra Azure resources.

Agents must apply these rules before proposing or performing a cloud-dev deployment:

- Batch related code changes into one cloud image when practical.
- Build and test the image locally before pushing to ACR.
- Keep `acrstatsdev001` on Basic SKU unless the user explicitly approves a change.
- Keep the Container App in single active revision mode for the fast cloud-dev lane unless rollback testing requires a temporary multi-revision setup.
- Keep cloud-dev scale-to-zero/min-replica behavior; do not add always-on replicas without explicit user approval.
- Do not increase CPU or memory as a first response to slow OCR or parsing; profile and optimize code/config first.
- Prefer focused cloud smoke tests over repeated full cloud regression runs.
- Use descriptive temporary tags for candidate deployments, then prune old non-active tags when the user approves cleanup.
- Record whether a deployment is expected to create new standing monthly cost. Existing-image redeploys should normally say `No new standing Azure resource cost`.
- Do not create additional Blob Storage, Fabric, Power BI, additional Container Apps, Dedicated workload profiles, or premium SKUs unless the user explicitly asks and accepts the cost/risk.

### 9. External Review Coordination

Claude, Copilot, or other review tools can be used as reviewer agents.

Reviews should be treated as advisory until triaged, not automatically accepted or automatically ignored.

For each review, record:

- reviewer/tool name,
- date,
- files or scope reviewed,
- findings,
- severity,
- accepted/rejected/deferred decision,
- reason for the decision,
- fix commit or file changes when applicable,
- whether the finding blocks `cloud-dev` deployment.

Review findings should block `cloud-dev` deployment when they involve:

- failing runtime startup,
- broken module or Stats Web health checks,
- secrets or credentials,
- incorrect cloud configuration,
- database migration/data-loss risk,
- authentication/authorization regressions,
- container packaging failures,
- high-risk test failures.

Review findings may be deferred when they are:

- style-only,
- larger refactors outside the module scope,
- production hardening better suited for `prod-sim`,
- known limitations already documented with an owner.

Review notes can live near the module evidence, architecture-hardening review folders, or a module-specific review file. The important rule is that the final agent handoff must say what review feedback remains unresolved.

### 10. Cloud Smoke Tests

After cloud-dev deployment exists, agents should use smoke tests appropriate to their changes:

- public `/health`,
- relevant page load,
- relevant module health endpoint through Stats Web if exposed,
- simple feature path,
- log check for errors and secret leakage.

### 11. Evidence

Agents should record cloud-impacting work in the appropriate evidence or module notes.

Minimum evidence for a cloud-dev deployment:

- image reference,
- test summary,
- deployment/revision identifier when Container Apps exists,
- `/health` result,
- log check summary,
- known limitations.

## Prompt For Other Codex Chats

Use this prompt at the start of another module chat:

```text
We now have a shared Azure cloud-dev baseline for the Stats app.

Treat this Codex chat as an agent working on one part of the same deployable app. Continue developing locally first, but make all runtime-affecting changes cloud-dev aware.

Read and follow:
- docs/cloud-dev-development-rules.md
- docs/M14-student-production-ci-cd-plan.md
- docs/M14-azure-development-continuation-plan.md
- infrastructure/cloud/cloud-dev-stage1-evidence.md

Current cloud-dev baseline:
- resource group: rg-stats-dev
- region: australiaeast
- ACR: acrstatsdev001
- active image pattern: acrstatsdev001.azurecr.io/stats-runtime:dev-*
- Container App: ca-stats-dev-001
- Azure SQL database: sqldb-stats-dev
- Key Vault: kv-stats-dev-001
- reporting: Fabric/Power BI integration has MVP evidence
- storage: Azure Blob Storage is the cloud durability target, but document/email attachment durability still needs evidence

Do not create or mutate Azure resources unless I explicitly ask in this chat.

For your module work:
1. Work locally first.
2. Run focused tests.
3. If you use Claude, Copilot, or another reviewer, triage the findings and state what is accepted, fixed, rejected, deferred, or still blocking.
4. If you add runtime config, update config/stats.runtime.json and infrastructure/cloud/azure-container-apps.env.example.
5. If you affect database/storage/cloud behavior, document the cloud-dev impact.
6. Before proposing a cloud-dev deployment, report files changed, tests run, review status, env/config changes, database/storage impact, image rebuild need, proposed image tag, and smoke tests.
7. Do not deploy directly to prod-sim; prod-sim is for later production-style learning.
```

<!-- M14 - Cloud Readiness End -->
