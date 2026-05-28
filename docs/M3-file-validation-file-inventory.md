<!-- M3 - File Validation Module Start -->
<!-- Documents files created for the merged M3/M4 file validation and ingestion module. -->

# M3/M4 File Validation and Ingestion File Inventory

## Summary

This document lists the files created and modified for the merged **M3 File Validation** and **M4 File Ingestion** module and describes the purpose of each addition.

## Specification and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M3-file-validation-module-spec.md` | Created/Modified | Defines the merged M3/M4 goals, boundaries, configuration, API contracts, findings, tests, and acceptance criteria. |
| `docs/M3-file-validation-file-inventory.md` | Created/Modified | Documents the files created and modified for the merged M3/M4 intake module. |
| `contracts/documents/README.md` | Modified | Adds the concrete validation and ingestion request/result contract summaries. |
| `docs/M3-file-validation-activity-flow.md` | Created | Provides the swimlane activity flow, including automatic validation after file selection. |

## Standalone Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/file-validation-module/README.md` | Created/Modified | Documents local runtime, tests, configuration, validation behavior, and ingestion behavior. |
| `modules/file-validation-module/requirements.txt` | Created | Lists FastAPI, multipart upload, config, and test dependencies. |
| `modules/file-validation-module/config/defaults.env` | Created/Modified | Provides safe committed defaults for local validation policy and ingestion storage/runtime settings. |
| `modules/file-validation-module/.env.example` | Created/Modified | Provides local override examples. |
| `modules/file-validation-module/app/main.py` | Created/Modified | Starts the merged File Validation and Ingestion API. |
| `modules/file-validation-module/app/config.py` | Created/Modified | Loads runtime settings from defaults, optional local overrides, and environment variables. |
| `modules/file-validation-module/app/models/common.py` | Created | Defines health and root metadata schemas. |
| `modules/file-validation-module/app/models/validation.py` | Created | Defines validation policy, metadata, finding, and result schemas. |
| `modules/file-validation-module/app/models/ingestion.py` | Created | Defines ingestion status, source context, handoff, finding, and record schemas. |
| `modules/file-validation-module/app/routes/health.py` | Created | Provides health and root endpoints. |
| `modules/file-validation-module/app/routes/validation.py` | Created | Provides the file validation upload endpoint. |
| `modules/file-validation-module/app/routes/ingestions.py` | Created | Provides ingestion creation and status lookup endpoints. |
| `modules/file-validation-module/app/services/validation_service.py` | Created | Implements reusable policy-driven validation checks and signature detection. |
| `modules/file-validation-module/app/services/ingestion_service.py` | Created | Implements ingestion record creation, idempotency handling, configured storage, and status lookup. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `modules/file-validation-module/tests/conftest.py` | Created/Modified | Provides the FastAPI test client fixture and resets ingestion test state. |
| `modules/file-validation-module/tests/test_foundation.py` | Created/Modified | Verifies app import, health/root endpoints, and settings defaults. |
| `modules/file-validation-module/tests/test_validation_service.py` | Created | Verifies core validation behavior for accepted and rejected files. |
| `modules/file-validation-module/tests/test_validation_api.py` | Created | Verifies the multipart validation API and request policy override behavior. |
| `modules/file-validation-module/tests/test_ingestion_api.py` | Created | Verifies ingestion creation, status lookup, rejected validation handling, and idempotent duplicate behavior. |

## Stats Web Integration Surface

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/appsettings.json` | Modified | Adds the configured File Validation and Ingestion API base URLs for local validation and intake. |
| `apps/stats-web/Program.cs` | Modified | Adds `FileValidationBaseUrl` to the Stats Web downstream configuration options. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Enables file selection and prepares automatic validation result states without implementing parsing. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Exposes the configured validation API base URL to the upload page. |
| `apps/stats-web/wwwroot/js/upload.js` | Created | Automatically calls M3 validation when a file is selected and renders accepted/rejected states. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Styles selected-file summaries and validation result states. |
| `apps/stats-data/README.md` | Modified | Documents that accepted intake files live under configured `STORAGE_ROOT` as Stats-owned data. |
| `tests/integration/test_stats_web_orchestration_config.py` | Modified | Verifies Stats Web uses one merged file intake service for validation and ingestion. |

## Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `tests/results/M3-FileValidation/M3-FileValidation-test-results-2026-05-24.md` | Created | Summarizes M3 verification, Stats Web build verification, and M0/M1 regression results. |
| `tests/results/M3-FileValidation/M3-FileValidation-test-raw-output-2026-05-24.txt` | Created | Stores raw `pytest` output for the M3 File Validation Module. |
| `tests/results/M3-FileValidation/M3-StatsWeb-upload-integration-build-raw-output-2026-05-24.txt` | Created | Stores raw `dotnet build` output for the Stats Web upload integration surface. |
| `tests/results/M3-FileValidation/M3-M0-regression-raw-output-2026-05-24.txt` | Created | Stores carried-forward M0 architecture regression output. |
| `tests/results/M3-FileValidation/M3-M1-regression-raw-output-2026-05-24.txt` | Created | Stores carried-forward M1 identity regression output. |
| `tests/results/M3-FileValidation/M3-live-database-regression-raw-output-2026-05-24.txt` | Created | Stores the live Stats database identity regression output. |
| `tests/results/M3-FileValidation/M3-FileValidation-manual-test-checklist.md` | Created | Records manual/API/UI validation expectations for M3. |
| `tests/results/M3-FileValidation/M3-FileValidation-screenshot-evidence-2026-05-24.md` | Created | Indexes current raw evidence and lists the planned Windows screenshot targets for the full browser evidence session. |

## Verification

Run from:

```powershell
C:\000_Capstone\modules\file-validation-module
```

Command:

```powershell
pytest
```

<!-- M3 End -->
