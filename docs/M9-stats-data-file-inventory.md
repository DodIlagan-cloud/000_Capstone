<!-- M9 - Stats Data and Persistence Start -->
<!-- Documents files created or modified for M9 Stats Data and Azure SQL. -->

# M9 Stats Data File Inventory

## Summary

M9 owns the Stats product persistence layer. The current cloud-dev direction is Azure SQL Database.

## Files

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M9-stats-data-persistence-module-spec.md` | Created / Updated | Defines M9 schema, persistence boundaries, Azure SQL migration requirements, API contract, config, testing, and acceptance criteria. Updated on 2026-06-11 to require plain-language recognition approval failures and production-like cleanup of evidence/test residue. |
| `docs/M9-stats-data-erd.md` | Created / Updated | Draft ERD for Stats-owned product tables, the M1 user reference boundary, and the pre-save duplicate-check result tables. |
| `docs/M9-stats-data-file-inventory.md` | Created | This file. Tracks M9 persistence and Azure SQL assets. |
| `apps/stats-data/migrations/azure-sql/README.md` | Created | Documents the Azure SQL migration folder and no-secret boundary. |
| `apps/stats-data/migrations/azure-sql/001_initial_stats_data_schema.sql` | Created | Initial Azure SQL schema for M9 product data tables, indexes, JSON checks, migration tracking, and dashboard-ready query fields. |
| `apps/stats-data/migrations/azure-sql/002_validation_reporting_schema.sql` | Created | Adds Azure SQL structures for the evolved validation handoff: source sections, entities, references, installments, reason-code JSON, source confidence fields, and enriched validation summary counts. |
| `apps/stats-data/migrations/azure-sql/005_duplicate_check_results.sql` | Created | Adds document fingerprints and duplicate-check batch/result tables for pre-save document and transaction duplicate review. |
| `apps/stats-data/migrations/azure-sql/006_document_processing_jobs.sql` | Created | Adds durable upload processing-job tracking so cloud Upload workflows can poll M5/M7/M8 progress instead of holding one long browser request open. |
| `apps/stats-data/migrations/azure-sql/007_document_processing_steps.sql` | Created | Adds durable per-step timing rows for upload processing jobs, including module/boundary name, step name, status, start/end timestamps, duration, safe metadata, and sanitized error details. |
| `apps/stats-data/migrations/azure-sql/009_recognition_label_governance.sql` | Created/Modified | Adds pending recognition suggestion and synchronization governance structures. Planned alignment: suggestions remain separate from active transaction/document labels until admin approval. |
<!-- M9 Recognition Settings Persistence Start - 2026-06-10 -->
| `apps/stats-data/migrations/azure-sql/010_active_recognition_settings.sql` | Created/Modified | Adds active database-backed recognition labels/rules to replace runtime JSON as the source of truth. Baseline document, transaction, and spending settings are seeded into Azure SQL before M5/M7 consume active settings. |
| `apps/stats-data/scripts/apply_azure_sql_migrations.py` | Created | Applies Azure SQL/T-SQL migration files inside the runtime container using `AZURE_SQL_CONNECTIONSTRING` without printing secret values. |
| `apps/stats-data/src/stats_data/api.py` | Created/Modified | Exposes the Stats Data API, including `POST /api/v1/transactions/batches` for reviewed validation-result persistence and admin recognition-settings endpoints for active settings, label/rule add/edit/delete, suggestion reads, and sync preview. |
| `apps/stats-data/src/stats_data/database.py` | Created | Normalizes Azure SQL ODBC connection settings and opens provider-checked Azure SQL connections without printing secret values. |
| `apps/stats-data/src/stats_data/main.py` | Created | Stats Data API runtime entrypoint for the container startup script. |
| `apps/stats-data/src/stats_data/duplicate_checks.py` | Created / Updated | Builds document fingerprints, checks reviewed validation records against existing M9 documents and transactions, persists duplicate-check results, and returns a per-row review summary before save. Review hardening treats empty duplicate keys/fingerprints as missing evidence, batches exact duplicate-key lookup, and derives result IDs from row/match content instead of list position. |
| `apps/stats-data/src/stats_data/processing_jobs.py` | Created / Updated | Creates, updates, and reads M9 processing-job records used by Stats Web async upload polling; appends and reads durable processing-step timing summaries. Timing rows attached to already-successful save/check operations are operational evidence and must not fail the primary operation. Review hardening closes cursors on failed writes and prevents terminal jobs from being overwritten by later non-terminal updates. |
| `apps/stats-data/src/stats_data/recognition_settings.py` | Created/Modified | M9 recognition settings adapter/API helper for active labels, rules, pending suggestions, approval/rejection, and sync-preview behavior. Seeds baseline values from migration/reference configuration into database-backed active settings and returns the M5/M7 runtime payload shape. |
| `apps/stats-data/src/stats_data/validation_persistence.py` | Created / Updated | Builds deterministic validation staging/promoted-row persistence plans, writes temporary validation handoff payload files, persists from those files, performs best-effort cleanup after successful Azure SQL commits, and executes idempotent Azure SQL upserts without resetting promotion or non-empty storage state on retry. Review hardening keeps recent-document pagination inside the same SQL statement so the configured limit is applied. |
| `apps/stats-web/Program.cs` | Updated | Routes same-origin `/api/v1/transactions/batches` and `/api/v1/transactions/duplicate-checks` requests to the container-internal Stats Data API. Async upload work adds a Stats Web background workflow endpoint that starts M5/M7/M8 processing without holding one cloud browser request open, avoids forcing the previous single-page parse workaround, logs structured per-step durations, persists safe timing summaries through M9, and deletes the temporary upload file if the initial processing-step write fails before the background job starts. |
| `apps/stats-web/Pages/Upload.cshtml` | Updated | Exposes the Stats Data base URL to the Upload page. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Updated | Supplies the configured Stats Data downstream URL to Upload page markup. |
| `apps/stats-web/wwwroot/js/upload.js` | Updated | Enables `Save ready transactions` after review readiness, calls the M9 pre-save duplicate-check endpoint, surfaces duplicate review counts and row-level duplicate messages instead of a generic save failure, sends the edited validation payload plus authenticated user context to M9, reports downstream parse-service error details, and resets the upload picker after terminal failure or save. Async upload work starts a processing job and polls status instead of waiting on a long M5 parse request; it does not send the old `page_limit=1` timeout workaround. |
| `infrastructure/containers/stats/Dockerfile` | Updated | Packages M9 migrations, scripts, adapter source, cloud-dev contract documents, and Stats Web source assets needed by container-run contract tests; installs Azure SQL ODBC dependencies; and keeps runtime intake data out of the image. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Updated | Waits for Azure SQL, applies M9 migrations, then initializes M1 identity tables before starting module APIs and Stats Web. |
| `.dockerignore` | Updated | Excludes `apps/stats-data/data/` runtime intake files from Docker build context. |
| `tests/scripts/M13-Containerization/run_docker_acceptance_evidence.ps1` | Updated | Replaces historical `stats-db`/`psql` check with an in-container Azure SQL `dbo.users` verification. |
| `tests/scripts/regression/run_docker_full_regression_evidence.ps1` | Updated | Runs official database checks inside `stats-runtime` against Azure SQL without printing connection secrets. |
| `infrastructure/cloud/cloud-dev-azure-sql-evidence.md` | Created | Records the created cloud-dev Azure SQL, Key Vault, firewall, Entra admin, and secret names without secret values. |
| `tests/integration/test_m9_azure_sql_contract.py` | Created / Updated | Verifies the Azure SQL migration, cloud config, identity database provider boundary, startup readiness script, Compose runtime shape, container driver dependencies, and review follow-up table-order checks for transaction and processing-run foreign-key dependents without requiring live credentials. |
| `tests/unit/stats_data/test_validation_persistence.py` | Created / Updated | Verifies the validation persistence adapter from configured real `tests/input` files by running M5 parsing, M7 extraction, and validation before building the M9 persistence plan. The live Azure SQL write test runs only when `AZURE_SQL_CONNECTIONSTRING` is configured. |
| `tests/unit/stats_data/test_stats_data_api.py` | Created | Verifies the Stats Data API save response using a validation payload produced from configured real `tests/input` files. |
| `tests/unit/stats_data/test_stats_data_api.py` | Modified | Adds focused API tests for active recognition settings and spec-named document label/rule endpoints without requiring live Azure SQL. |
| `tests/unit/stats_data/test_validation_persistence.py` | Modified | Aligns source-candidate traceability expectation with the current M8/M9 contract: `source_candidate_id` points to the M7 candidate while `record_id` remains the M8 normalized record identifier. |
<!-- M9 Recognition Settings Persistence End - 2026-06-10 -->

<!-- M9 AI Suggestion Approval Start - 2026-06-11 -->
| `apps/stats-data/src/stats_data/recognition_settings.py` | Modified | Adds pending suggestion persistence and admin approval/rejection helpers that update active database-backed labels and linked fallback transactions. |
| `apps/stats-data/src/stats_data/validation_persistence.py` | Modified | Persists M8-carried recognition suggestion metadata into `dbo.recognition_label_suggestions` alongside saved transactions. |
| `apps/stats-data/src/stats_data/api.py` | Modified | Exposes admin approval/rejection endpoint for recognition suggestions. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml.cs` | Modified | Loads pending recognition suggestions and posts admin approval/rejection actions through M9. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml` | Modified | Shows pending AI/user recognition suggestions in the admin recognition settings page. |
| `tests/unit/stats_data/test_stats_data_api.py` | Modified | Adds API coverage for recognition suggestion approval. |
| `tests/unit/stats_data/test_validation_persistence.py` | Modified | Adds persistence-plan coverage for recognition suggestion rows. |
<!-- M9 Document Suggestion Approval Start - 2026-06-11 -->
| `apps/stats-data/migrations/azure-sql/011_document_recognition_suggestions.sql` | Created | Adds document-level recognition suggestion columns and expands suggestion rows with proposed document type/subtype fields. |
| `apps/stats-data/src/stats_data/recognition_settings.py` | Modified | Extends approval/rejection helpers to activate approved document labels and synchronize linked saved documents/validation results that still use fallback document types. |
| `apps/stats-data/src/stats_data/validation_persistence.py` | Modified | Persists M8-carried document-label suggestion metadata into `dbo.recognition_label_suggestions` and links saved document rows to the pending suggestion. |
| `apps/stats-data/src/stats_data/api.py` | Modified | Returns document suggestion fields through the admin recognition suggestion API. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml.cs` | Modified | Loads document suggestion fields for the admin review page. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml` | Modified | Displays pending document-type suggestions alongside transaction and spending suggestions. |
| `apps/stats-web/wwwroot/js/classifications.js` | Modified | Converts failed async recognition-setting and suggestion-review responses into plain-language admin messages instead of raw HTTP status text. |
| `tests/scripts/regression/cleanup_m5_m7_m9_recognition_evidence_data_2026_06_11.py` | Created | Cleans evidence-only recognition labels, suggestions, upload documents, processing jobs, validation rows, transaction rows, and the evidence admin account from Azure SQL through `stats-runtime` without printing secrets. |
| `tests/scripts/regression/run_m5_m7_m9_recognition_approval_desktop_evidence_2026_06_11.py` | Modified | Keeps screenshot evidence full-flow, adds friendly stale-review failure text, and restores/cleans recognition test state after failed runs. |
<!-- M9 Document Suggestion Approval End - 2026-06-11 -->
<!-- M9 AI Suggestion Approval End - 2026-06-11 -->
<!-- M9 Recognition Approval Evidence Update Start - 2026-06-11 -->
| `tests/scripts/regression/cleanup_m5_m7_m9_recognition_evidence_data_2026_06_11.py` | Modified | Cleans evidence residue from Azure SQL and restores core document/transaction/spending labels before each full-flow evidence run without printing secrets. |
| `tests/scripts/regression/run_m5_m7_m9_recognition_approval_desktop_evidence_2026_06_11.py` | Modified | Uses one Edge Stats app instance for the UI workflow and captures DB query evidence from `stats-runtime` against Azure SQL for added, removed, suggested, approved, and synchronized records. |
| `tests/results/M5-M7-M9-RecognitionApproval/M5-M7-M9-recognition-approval-2026-06-11-20260611-130431/` | Created | Final desktop evidence proving Azure SQL label activation, suggestion approval records, linked document update, and linked transaction update after admin approval. |
<!-- M9 Recognition Approval Evidence Update End - 2026-06-11 -->
| `tests/results/M9-StatsDataPersistence/M9FullWorkflow-M0-M9/` | Created / Moved | Centralized M9 full-workflow evidence output folder. This was moved out of `apps/stats-data/test-results/` so M9 follows the project rule that evidence and validation outputs live under the root `tests/results` tree. |

<!-- M9 Recognition Governance Hardening Start - 2026-06-12 -->

## Recognition Governance Hardening

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M9-stats-data-persistence-module-spec.md` | Modified | Requires terminal one-time suggestion review, linked config-change/sync-run audit IDs, honest label-rename failures, and idempotent recognition settings seeding. |
| `apps/stats-data/src/stats_data/recognition_settings.py` | Modified | Links sync-run rows to real config-change IDs, prevents duplicate review audit rows for terminal suggestions, reports missing rename source labels, and seeds labels/rules through idempotent `MERGE ... WITH (HOLDLOCK)` operations. |
| `tests/unit/stats_data/test_recognition_settings.py` | Created | Verifies audit linkage, terminal review no-op behavior, rename not-found behavior, and idempotent seed SQL shape. |

<!-- M9 Recognition Governance Hardening End - 2026-06-12 -->

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
