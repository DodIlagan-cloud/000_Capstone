# Stats Architecture Baseline

## Purpose

This document is the current hardened architecture baseline for the Stats capstone project.

The project remains spec-driven: module specs drive implementation. When an architecture decision changes the expected shape of the project, the affected specs must be updated first. Development resumes only after the specs reflect the current baseline.

## Active Architecture

Only these repository roots are active architecture surfaces:

| Root | Responsibility |
| --- | --- |
| `apps/` | Stats product applications such as Stats Web and Stats Data. |
| `modules/` | Reusable backend building-block modules. |
| `contracts/` | Explicit handoff contracts between apps and modules. |
| `config/` | Central runtime, path, and logging registries. |
| `infrastructure/` | Container, Compose, and later cloud deployment assets. |
| `tests/` | Root-owned unit, integration, evidence scripts, fixtures, and results. |
| `docs/` | Specs, plans, inventories, evidence guidance, and project reports. |
| `samples/` | Approved safe sample data. |

Historical or retired implementation paths must not appear in active module specs as implementation guidance. If historical context is needed, keep it in file inventories or history notes only.

## Module Architecture

| Module | Active Owner | Runtime Shape | Baseline Rule |
| --- | --- | --- | --- |
| M0 Foundation | `docs/`, `config/`, `tests/` | Project governance | Defines spec-first, config, logging, evidence, and container-first rules. |
| M1 Identity Access | `modules/identity-access-module/` | FastAPI inside `stats-runtime` | Owns identity contracts and auth behavior; database target is configured centrally. |
| M2 Stats Web Shell | `apps/stats-web/` | ASP.NET Core inside `stats-runtime` | Owns UI/orchestration shell; calls module APIs through configured endpoints/proxy settings. |
| M3/M4 File Validation and Ingestion | `modules/file-validation-module/` | FastAPI inside `stats-runtime` | Owns validation/intake behavior; storage root/provider is centrally configured. |
| M5 Document Parsing | `modules/document-parsing-module/` | FastAPI + OCR inside `stats-runtime` | Owns text/OCR/classification behavior; OCR settings are centrally registered. |
| M7 Transaction Extraction | `modules/transaction-extraction-module/` | FastAPI inside `stats-runtime` | Owns extraction candidate behavior; limits and thresholds are centrally registered. |
| M8 Data Validation | `modules/data-validation-module/` | FastAPI inside `stats-runtime` | Owns normalization and request-local validation; thresholds are centrally registered. |
| M9 Stats Data and Persistence | `apps/stats-data/` | Product data module | Owns schema, migrations, persistence adapters, and stored workflow results. |
| M10 Stats Workflow Integration | Stats product layer | Container-first integration | Connects upload, validation, parsing, extraction, validation, and persistence through contracts. |
| M11 Dashboard and Reporting | `apps/stats-web/` plus Stats Data queries | ASP.NET Core UI | Presents persisted workflow and reporting data without absorbing processing internals. |
| M13 Containerization | `infrastructure/` | `stats-runtime` plus `stats-db` | Runs all active modules in the app container and PostgreSQL in a separate DB container. |
| M14 Cloud Readiness | `infrastructure/cloud/` | Later iteration | Maps central config to Azure app config, Key Vault, PostgreSQL, Blob Storage, and monitoring. |

## Configuration Baseline

`config/stats.runtime.json` is the central runtime configuration registry.

Module-local `config/defaults.env` files are still required because modules are reusable and should remain runnable in isolation. However, they are projections of the central registry. A module-local config key is valid only when it is declared in the central runtime registry.

Configuration precedence is:

1. Central registry defines approved keys, ownership, secret status, and safe defaults.
2. Module `config/defaults.env` supplies module-local safe defaults using approved keys.
3. Module `.env` supplies uncommitted local overrides.
4. Environment variables, container env files, or later managed cloud providers override runtime values.

No runtime value that changes by machine, container, cloud environment, secret rotation, deployment target, port conflict, or fixture location should be embedded as an application-code literal.

## Path Baseline

`config/stats.paths.json` is the logical path map. `STATS_APP_ROOT` is the physical runtime root.

The same logical path should work whether the physical root is local development, `/app` inside Docker, or a later cloud runtime. Durable files should move behind `STATS_STORAGE_PROVIDER` so local filesystem storage can later become Azure Blob Storage without changing module business logic.

## Logging Baseline

`config/stats.logging.json` is the central logging contract.

Modules may keep local logging setup code, but it must follow the central logging registry:

- Log level is configured through `LOG_LEVEL`.
- Logs go to stdout/stderr for container and later cloud collection.
- Sensitive values are redacted.
- Request or correlation identifiers are included when available.
- Raw OCR text, credentials, tokens, account numbers, card numbers, and database connection strings are not logged.

## Database Baseline

The database is separate from the app runtime.

Local/container MVP:

```text
stats-runtime  -> Stats Web, module APIs, OCR
stats-db       -> PostgreSQL with persistent volume
```

Cloud target:

```text
Stats app runtime      -> Azure App Service, Azure Container Apps, or equivalent
Managed PostgreSQL     -> Azure Database for PostgreSQL
Durable file storage   -> Azure Blob Storage
Secrets/config         -> Azure Key Vault or managed app configuration
```

M13 owns local container wiring. M9 owns schema, migrations, persistence adapters, and product data ownership. M14 owns cloud deployment mapping.

## Container Baseline

From M13 onward, official module acceptance, regression, OCR, database, browser, and capstone evidence runs through the Stats Docker runtime. Host-side runs are diagnostics only unless a spec explicitly says otherwise for a non-runtime check.

## Sanity Check Rules

- Active specs describe the active architecture, not migration history.
- Historical paths belong in inventories or history notes, not current implementation guidance.
- Every module-local config key must be declared centrally.
- Logging behavior must be centrally governed even when implemented locally.
- Database runtime settings are centralized; schema ownership belongs to M9.
- New module specs must start from the hardened module template.
