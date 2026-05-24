<!-- M3 - File Validation Module Start -->
<!-- Documents files created for Module 3 file validation. -->

# M3 File Validation File Inventory

## Summary

This document lists the files created for **M3 - File Validation Module** and describes the purpose of each addition.

## Specification and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M3-file-validation-module-spec.md` | Created | Defines the Module 3 goals, boundaries, configuration, API contract, findings, tests, and acceptance criteria. |
| `docs/M3-file-validation-file-inventory.md` | Created | Documents the files created for M3. |
| `contracts/documents/README.md` | Modified | Adds the concrete M3 file validation request/result contract summary. |
| `docs/M3-file-validation-activity-flow.md` | Created | Provides the swimlane activity flow, including automatic validation after file selection. |

## Standalone Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/file-validation-module/README.md` | Created | Documents local runtime, tests, and configuration. |
| `modules/file-validation-module/requirements.txt` | Created | Lists FastAPI, multipart upload, config, and test dependencies. |
| `modules/file-validation-module/config/defaults.env` | Created | Provides safe committed defaults for local validation runtime and policy. |
| `modules/file-validation-module/.env.example` | Created | Provides local override examples. |
| `modules/file-validation-module/app/main.py` | Created | Starts the standalone File Validation API. |
| `modules/file-validation-module/app/config.py` | Created | Loads runtime settings from defaults, optional local overrides, and environment variables. |
| `modules/file-validation-module/app/models/common.py` | Created | Defines health and root metadata schemas. |
| `modules/file-validation-module/app/models/validation.py` | Created | Defines validation policy, metadata, finding, and result schemas. |
| `modules/file-validation-module/app/routes/health.py` | Created | Provides health and root endpoints. |
| `modules/file-validation-module/app/routes/validation.py` | Created | Provides the file validation upload endpoint. |
| `modules/file-validation-module/app/services/validation_service.py` | Created | Implements reusable policy-driven validation checks and signature detection. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `modules/file-validation-module/tests/conftest.py` | Created | Provides the FastAPI test client fixture. |
| `modules/file-validation-module/tests/test_foundation.py` | Created | Verifies app import, health/root endpoints, and settings defaults. |
| `modules/file-validation-module/tests/test_validation_service.py` | Created | Verifies core validation behavior for accepted and rejected files. |
| `modules/file-validation-module/tests/test_validation_api.py` | Created | Verifies the multipart validation API and request policy override behavior. |

## Stats Web Integration Surface

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/appsettings.json` | Modified | Adds the configured File Validation Module base URL for local automatic validation. |
| `apps/stats-web/Program.cs` | Modified | Adds `FileValidationBaseUrl` to the Stats Web downstream configuration options. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Enables file selection and prepares automatic validation result states without implementing parsing. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Exposes the configured validation API base URL to the upload page. |
| `apps/stats-web/wwwroot/js/upload.js` | Created | Automatically calls M3 validation when a file is selected and renders accepted/rejected states. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Styles selected-file summaries and validation result states. |

## Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `test-results/M3-FileValidation/M3-FileValidation-test-results-2026-05-24.md` | Created | Summarizes M3 verification, Stats Web build verification, and M0/M1 regression results. |
| `test-results/M3-FileValidation/M3-FileValidation-test-raw-output-2026-05-24.txt` | Created | Stores raw `pytest` output for the M3 File Validation Module. |
| `test-results/M3-FileValidation/M3-StatsWeb-upload-integration-build-raw-output-2026-05-24.txt` | Created | Stores raw `dotnet build` output for the Stats Web upload integration surface. |
| `test-results/M3-FileValidation/M3-M0-regression-raw-output-2026-05-24.txt` | Created | Stores carried-forward M0 architecture regression output. |
| `test-results/M3-FileValidation/M3-M1-regression-raw-output-2026-05-24.txt` | Created | Stores carried-forward M1 identity regression output. |
| `test-results/M3-FileValidation/M3-live-database-regression-raw-output-2026-05-24.txt` | Created | Stores the live Stats database identity regression output. |
| `test-results/M3-FileValidation/M3-FileValidation-manual-test-checklist.md` | Created | Records manual/API/UI validation expectations for M3. |
| `test-results/M3-FileValidation/M3-FileValidation-screenshot-evidence-2026-05-24.md` | Created | Indexes current raw evidence and lists the planned Windows screenshot targets for the full browser evidence session. |

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
