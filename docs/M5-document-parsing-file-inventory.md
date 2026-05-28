<!-- M5 - Document Parsing Module Start -->
<!-- Documents planned and completed files for the M5 Document Parsing Module. -->

# M5 Document Parsing File Inventory

## Summary

This document lists the files planned, created, or modified for **M5 Document Parsing**. It must be created with the M5 specification before implementation begins so module scope, file ownership, and evidence expectations are visible from the start.

Current status: **implementation pass complete** for the M5 module runtime, Stats Web upload flow integration, and targeted regression checks. M13 containerization remains planned as the production packaging track for portable OCR tooling.

## Specification and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Created | Defines M5 goals, boundaries, runtime configuration, API contract, OCR strategy rules, classification output, redaction, testing, M13 runtime alignment, and acceptance criteria. |
| `docs/M5-document-parsing-file-inventory.md` | Created | Documents planned and completed files for M5. |
| `docs/building-block-module-plan.md` | Planned Modified | Aligns the roadmap so M5 is the merged Document Parsing module and former M6 classification is included in M5. |
| `docs/building-block-module-io-map.md` | Planned Modified | Defines the M5 input/output contract from file intake to transaction processing. |
| `contracts/extraction/README.md` | Planned Modified | Adds the concrete M5 Document Parsing request/result contract summary. |

## Standalone Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/README.md` | Created | Documents local runtime, tests, configuration, OCR dependency behavior, and module boundary. |
| `modules/document-parsing-module/requirements.txt` | Created | Lists FastAPI, PDF parsing, OCR adapter, PDF rendering, config, and test dependencies. |
| `modules/document-parsing-module/config/defaults.env` | Created | Provides safe committed defaults for local parsing runtime settings. |
| `modules/document-parsing-module/.env.example` | Created | Provides local override examples for OCR, Tesseract, test data, and runtime ports. |
| `modules/document-parsing-module/app/main.py` | Created | Starts the Document Parsing API. |
| `modules/document-parsing-module/app/config.py` | Created | Loads runtime settings from defaults, optional local overrides, and environment variables. |
| `modules/document-parsing-module/app/models/common.py` | Created | Defines health, root metadata, and OCR readiness schemas. |
| `modules/document-parsing-module/app/models/parsing.py` | Created | Defines parsing response, classification, quality, evidence, findings, and evaluation schemas. |
| `modules/document-parsing-module/app/routes/health.py` | Created | Provides health and root endpoints. |
| `modules/document-parsing-module/app/routes/parsing.py` | Created | Provides the document parsing upload endpoint. |
| `modules/document-parsing-module/app/services/parsing_service.py` | Created | Implements PDF text extraction, OCR fallback, scanned PDF rendering, findings, and evaluation metadata. |
| `modules/document-parsing-module/app/services/classification_service.py` | Created | Implements document type classification for supported financial document types. |
| `modules/document-parsing-module/app/services/redaction_service.py` | Created | Implements evidence redaction helpers for ethical data handling. |

## Stats Web Integration Surface

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/appsettings.json` | Modified | Adds the configured Document Parsing API base URL and local orchestration entry. |
| `apps/stats-web/Program.cs` | Modified | Adds `DocumentParsingBaseUrl` to Stats Web downstream configuration. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Removes the manual parse/send button and displays parse summary plus full M5 JSON output. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Exposes the configured parsing API base URL to the upload page. |
| `apps/stats-web/wwwroot/js/upload.js` | Modified | Runs validate -> ingest -> parse automatically and renders the M5 JSON output. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Styles parse result and JSON output states. |
| `tests/integration/test_stats_web_orchestration_config.py` | Modified | Verifies Stats Web knows the M5 local service endpoint. |
| `modules/file-validation-module/app/routes/ingestions.py` | Created | Restores the File Intake ingestion API surface required by the seamless validate -> ingest -> parse flow. |

## M13 Runtime Alignment Surface

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Planned Created/Modified | Records that M13 starts early as a single-container runtime slice for portable M5 OCR tooling. |
| `infrastructure/containers/stats/Dockerfile` | Planned Created | Packages Stats Web, module APIs, Tesseract, OCR language data, and Python OCR dependencies in one top-level Stats container. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Planned Created | Starts internal module APIs before Stats Web in the single runtime container. |
| `infrastructure/compose/stats-runtime.compose.yml` | Planned Created | Provides local production-like runtime validation for the top-level Stats container. |
| `tests/integration/test_m13_containerization_contract.py` | Planned Created | Verifies the portable OCR/runtime packaging contract. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/tests/conftest.py` | Created | Provides FastAPI test client fixtures and approved TestData lookup. |
| `modules/document-parsing-module/tests/test_foundation.py` | Created | Verifies app import, health/root endpoints, OCR readiness, and settings defaults. |
| `modules/document-parsing-module/tests/test_parsing_service.py` | Created | Verifies PDF text extraction, OCR paths, unavailable dependency behavior, classification, redaction, and evaluation fields. |
| `modules/document-parsing-module/tests/test_parsing_api.py` | Created | Verifies the multipart parsing API and trace metadata behavior. |

## Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `test-results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-test-results-YYYY-MM-DD.md` | Planned Created | Summarizes M5 automated, real-data, app-flow, and targeted regression verification. |
| `test-results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-test-raw-output-YYYY-MM-DD.txt` | Planned Created | Stores raw `pytest` output for the M5 module. |
| `test-results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-manual-test-checklist.md` | Planned Created | Tracks M5 manual/API/UI/evidence expectations. |
| `test-results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-screenshot-evidence-YYYY-MM-DD.md` | Planned Created | Indexes retained browser, terminal, app-flow, and JSON-output screenshots. |
| `test-results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-actual-app-flow-summary-YYYY-MM-DD.json` | Planned Created | Stores app-flow metadata using approved TestData without copying full sensitive document text into Markdown evidence. |


## Testing Boundary (M13)

From M13 onward, acceptance and evidence tests for this module run through the Docker stack:

| Tier | Where | Tool |
| --- | --- | --- |
| Unit / contract tests | Host machine | `pytest` |
| Acceptance / evidence | Docker stack | `tests\scripts\regression\run_docker_full_regression_evidence.ps1` |

Local unit tests remain the fast development feedback path and must not be removed.

## Verification

Executed module test command:

```powershell
cd $env:STATS_DOCUMENT_PARSING_MODULE_DIR
pytest
```

Result: **16 passed, 1 cache warning**.

Executed targeted Stats Web orchestration check:

```powershell
pytest tests\integration\test_stats_web_orchestration_config.py
```

Result: **4 passed, 1 cache warning**.

Executed touched File Intake regression with approved TestData:

```powershell
cd $env:STATS_FILE_VALIDATION_MODULE_DIR
pytest tests
```

Result: **17 passed, 1 cache warning**.

Executed Stats Web compile check:

```powershell
cd $env:STATS_WEB_DIR
dotnet build -o $env:STATS_M5_EVIDENCE_DIR\stats-web-build-check
```

Result: **build succeeded, 0 warnings, 0 errors**.

M13 containerization contract tests remain pending until the M13 single-container runtime files are implemented.

<!-- M5/M6 End -->
