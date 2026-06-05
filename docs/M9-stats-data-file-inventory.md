<!-- M9 - Stats Data and Persistence Start -->
<!-- Documents files created or modified for M9 Stats Data and Azure SQL. -->

# M9 Stats Data File Inventory

## Summary

M9 owns the Stats product persistence layer. The current cloud-dev direction is Azure SQL Database.

## Files

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M9-stats-data-persistence-module-spec.md` | Created / Updated | Defines M9 schema, persistence boundaries, Azure SQL migration requirements, API contract, config, testing, and acceptance criteria. |
| `docs/M9-stats-data-erd.md` | Created | Draft ERD for Stats-owned product tables and the M1 user reference boundary. |
| `docs/M9-stats-data-file-inventory.md` | Created | This file. Tracks M9 persistence and Azure SQL assets. |
| `apps/stats-data/migrations/azure-sql/README.md` | Created | Documents the Azure SQL migration folder and no-secret boundary. |
| `apps/stats-data/migrations/azure-sql/001_initial_stats_data_schema.sql` | Created | Initial Azure SQL schema for M9 product data tables, indexes, JSON checks, migration tracking, and dashboard-ready query fields. |
| `apps/stats-data/migrations/azure-sql/002_validation_reporting_schema.sql` | Created | Adds Azure SQL structures for the evolved validation handoff: source sections, entities, references, installments, reason-code JSON, source confidence fields, and enriched validation summary counts. |
| `apps/stats-data/scripts/apply_azure_sql_migrations.py` | Created | Applies Azure SQL/T-SQL migration files inside the runtime container using `AZURE_SQL_CONNECTIONSTRING` without printing secret values. |
| `apps/stats-data/src/stats_data/api.py` | Created | Exposes the Stats Data API, including `POST /api/v1/transactions/batches` for reviewed validation-result persistence. |
| `apps/stats-data/src/stats_data/database.py` | Created | Normalizes Azure SQL ODBC connection settings and opens provider-checked Azure SQL connections without printing secret values. |
| `apps/stats-data/src/stats_data/main.py` | Created | Stats Data API runtime entrypoint for the container startup script. |
| `apps/stats-data/src/stats_data/validation_persistence.py` | Created / Updated | Builds deterministic validation staging/promoted-row persistence plans, writes temporary validation handoff payload files, persists from those files, deletes them after successful Azure SQL commits, and executes idempotent Azure SQL upserts for validation results. |
| `apps/stats-web/Program.cs` | Updated | Routes same-origin `/api/v1/transactions/batches` requests to the container-internal Stats Data API. |
| `apps/stats-web/Pages/Upload.cshtml` | Updated | Exposes the Stats Data base URL to the Upload page. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Updated | Supplies the configured Stats Data downstream URL to Upload page markup. |
| `apps/stats-web/wwwroot/js/upload.js` | Updated | Enables `Save ready transactions` after review readiness and sends the edited validation payload plus authenticated user context to M9. |
| `infrastructure/containers/stats/Dockerfile` | Updated | Packages M9 migrations, scripts, and adapter source into the runtime image, installs Azure SQL ODBC dependencies, and keeps runtime intake data out of the image. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Updated | Waits for Azure SQL, applies M9 migrations, then initializes M1 identity tables before starting module APIs and Stats Web. |
| `.dockerignore` | Updated | Excludes `apps/stats-data/data/` runtime intake files from Docker build context. |
| `tests/scripts/M13-Containerization/run_docker_acceptance_evidence.ps1` | Updated | Replaces historical `stats-db`/`psql` check with an in-container Azure SQL `dbo.users` verification. |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Updated | Runs official database checks inside `stats-runtime` against Azure SQL without printing connection secrets. |
| `infrastructure/cloud/cloud-dev-azure-sql-evidence.md` | Created | Records the created cloud-dev Azure SQL, Key Vault, firewall, Entra admin, and secret names without secret values. |
| `tests/integration/test_m9_azure_sql_contract.py` | Created / Updated | Verifies the Azure SQL migration, cloud config, identity database provider boundary, startup readiness script, Compose runtime shape, container driver dependencies, and review follow-up table-order checks for transaction and processing-run foreign-key dependents without requiring live credentials. |
| `tests/unit/stats_data/test_validation_persistence.py` | Created / Updated | Verifies the validation persistence adapter from configured real `tests/input` files by running M5 parsing, M7 extraction, and validation before building the M9 persistence plan. The live Azure SQL write test runs only when `AZURE_SQL_CONNECTIONSTRING` is configured. |
| `tests/unit/stats_data/test_stats_data_api.py` | Created | Verifies the Stats Data API save response using a validation payload produced from configured real `tests/input` files. |
| `tests/results/M9-StatsDataPersistence/M9FullWorkflow-M0-M9/` | Created / Moved | Centralized M9 full-workflow evidence output folder. This was moved out of `apps/stats-data/test-results/` so M9 follows the project rule that evidence and validation outputs live under the root `tests/results` tree. |

## Verification

Run:

```powershell
pytest tests/integration/test_m9_azure_sql_contract.py
```

Review follow-up:

- Verified the migration creates `dbo.transactions` before `dbo.financial_evidence_links`.
- Verified the migration creates `dbo.processing_runs` before `dbo.findings`.
- Added a contract test so those FK-order assumptions remain guarded.

<!-- M9 End -->
