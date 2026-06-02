<!-- M5 - Document Parsing Module Start -->
<!-- Documents planned and completed files for the M5 Document Parsing Module. -->

# M5 Document Parsing File Inventory

## Summary

This document lists the files planned, created, or modified for **M5 Document Parsing**. It must be created with the M5 specification before implementation begins so module scope, file ownership, and evidence expectations are visible from the start.

Current status: **implementation pass complete** for the M5 module runtime, Stats Web upload flow integration, targeted regression checks, and the M7-aligned OCR quality improvement pass. M13 containerization is now the official runtime and testing path for portable OCR tooling and module evidence.

## Specification and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Created | Defines M5 goals, boundaries, runtime configuration, API contract, OCR strategy rules, classification output, redaction, testing, M13 runtime alignment, and acceptance criteria. |
| `docs/M5-document-parsing-file-inventory.md` | Created | Documents planned and completed files for M5. |
| `docs/M5-document-parsing-activity-flow.md` | Created | Provides the printable swimlane activity flow diagram for the merged M5 parsing, OCR, classification, redaction, and M7 handoff behavior. |
| `docs/building-block-module-plan.md` | Modified | Aligns the roadmap so M5 is the merged Document Parsing module and former M6 classification is included in M5. |
| `docs/building-block-module-io-map.md` | Modified | Defines the M5 input/output contract from file intake to transaction processing. |
| `contracts/extraction/README.md` | Modified | Adds the concrete M5 Document Parsing request/result contract summary. |
| `contracts/document-classification/README.md` | Created | Defines shared classification vocabulary ownership, module responsibilities, update lifecycle, and the developer-maintained limitation for unknown document shapes. |
| `config/document-classification.vocabulary.json` | Created/Modified | Provides the shared machine-readable document type/subtype vocabulary consumed by M5 and later stored/reported by M9/M11, including statement and receipt subtypes. |
| `config/document-classification.rules.json` | Created/Modified | Provides generic text-signal rules consumed by M5 after direct PDF text extraction or Tesseract OCR output, including payment-terminal receipt signals. |
| `.dockerignore` | Modified | Keeps real `tests/input` source files out of the Docker build context; container-first evidence runners copy approved local fixtures into the running container explicitly. |

## Standalone Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/README.md` | Created | Documents local runtime, tests, configuration, OCR dependency behavior, and module boundary. |
| `modules/document-parsing-module/requirements.txt` | Created | Lists FastAPI, PDF parsing, OCR adapter, PDF rendering, config, and test dependencies. |
| `modules/document-parsing-module/config/defaults.env` | Created/Modified | Provides safe committed defaults for local parsing runtime settings, including OCR PSM retry and quality thresholds. |
| `modules/document-parsing-module/.env.example` | Created | Provides local override examples for OCR, Tesseract, test data, and runtime ports. |
| `modules/document-parsing-module/app/main.py` | Created | Starts the Document Parsing API. |
| `modules/document-parsing-module/app/config.py` | Created/Modified | Loads runtime settings from defaults, optional local overrides, and environment variables, including OCR retry and quality scoring settings. |
| `modules/document-parsing-module/app/models/common.py` | Created | Defines health, root metadata, and OCR readiness schemas. |
| `modules/document-parsing-module/app/models/parsing.py` | Created/Modified | Defines parsing response, classification with document type/subtype, quality, evidence, findings, evaluation schemas, OCR quality metadata, OCR word-block layout evidence, and the M5-to-M7 handoff audit schema. |
| `modules/document-parsing-module/app/routes/health.py` | Created | Provides health and root endpoints. |
| `modules/document-parsing-module/app/routes/parsing.py` | Created | Provides the document parsing upload endpoint. |
| `modules/document-parsing-module/app/services/parsing_service.py` | Created/Modified | Implements PDF text extraction, OCR fallback, scanned PDF rendering, EXIF orientation handling, image preprocessing, orientation/PSM retry, OCR word-block capture, OCR quality scoring, findings, evaluation metadata, transaction-signal counting, and M7-readiness audit output. |
| `modules/document-parsing-module/app/services/classification_service.py` | Created/Modified | Implements document type/subtype classification from shared vocabulary/rules for both direct PDF text and Tesseract OCR output. |
| `modules/document-parsing-module/app/services/redaction_service.py` | Created | Implements evidence redaction helpers for ethical data handling. |

## Stats Web Integration Surface

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/appsettings.json` | Modified | Adds configured container-internal downstream API base URLs and keeps host-side local orchestration disabled by default. |
| `apps/stats-web/Program.cs` | Modified | Adds document parsing, transaction extraction, and data validation downstream configuration. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Displays a user-facing transaction check result after M8 validation while keeping raw M5/M7/M8 details behind developer details. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Exposes the configured parsing API base URL to the upload page. |
| `apps/stats-web/wwwroot/js/upload.js` | Modified | Runs validate -> ingest -> parse -> extract -> validate automatically and renders M8 transaction check results, including M5 subtype labels, with raw details hidden behind developer details. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Styles parse result and JSON output states. |
| `tests/integration/test_stats_web_orchestration_config.py` | Modified | Verifies Stats Web uses container-first downstream endpoints and keeps host-side process startup disabled by default. |
| `modules/file-validation-module/app/routes/ingestions.py` | Created | Restores the File Intake ingestion API surface required by the seamless validate -> ingest -> parse flow. |

## M13 Runtime Alignment Surface

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M13-containerization-module-spec.md` | Created/Modified | Records that M13 is the project-wide container-first runtime and testing path. |
| `docs/M13-container-first-testing-policy.md` | Created | Defines the project-wide rule that official module tests and evidence run through the container. |
| `infrastructure/containers/stats/Dockerfile` | Created/Modified | Packages Stats Web, module APIs, Tesseract, OCR language data, Python OCR dependencies, test scripts, and test inputs in one top-level Stats container. |
| `infrastructure/containers/stats/start-stats-runtime.sh` | Created/Modified | Starts internal module APIs before Stats Web in the single runtime container. |
| `infrastructure/compose/stats-runtime.compose.yml` | Created/Modified | Provides production-like runtime validation for the top-level Stats container. |
| `tests/integration/test_m13_containerization_contract.py` | Created | Verifies the portable OCR/runtime packaging contract. |

## Tests

| File | Change Type | Description |
| --- | --- | --- |
| `tests/unit/document_parsing_module/conftest.py` | Created/Modified | Provides FastAPI test client fixtures and approved actual-data lookup. Review hardening on 2026-06-02 keeps official container runs strict when fixture env vars are configured, while allowing explicit skips for unconfigured host-only diagnostics. |
| `tests/unit/document_parsing_module/test_foundation.py` | Created | Verifies app import, health/root endpoints, OCR readiness, and settings defaults. |
| `tests/unit/document_parsing_module/test_parsing_service.py` | Created/Modified | Verifies PDF text extraction, real `tests/input` OCR paths, unavailable dependency behavior, shared vocabulary/rule classification, redaction, evaluation fields, orientation retry findings, OCR quality metadata, and M7 handoff audit readiness/redaction. OCR behavior tests must use approved input fixtures rather than generated files or mocked OCR text. |
| `tests/unit/document_parsing_module/test_parsing_api.py` | Created/Modified | Verifies the multipart parsing API, trace metadata behavior, and M7 handoff audit fields. |
| `tests/scripts/M5-DocumentParsing/run_m5_all_inputs_manual_unit_2026_05_28.py` | Created | Repeatable manual unit-style runner for parsing every file under the approved `tests/input` directory and writing output artefacts under `tests/results`. |

## Evidence

| File | Change Type | Description |
| --- | --- | --- |
| `tests/results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-test-results-2026-05-28.md` | Created | Summarizes M5 automated, actual-data, app-flow, and targeted regression verification. |
| `tests/results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-test-raw-output-2026-05-28.txt` | Created | Stores raw `pytest` output for the M5 module. |
| `tests/results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-manual-test-checklist.md` | Created/Modified | Tracks M5 manual/API/UI/evidence expectations. |
| `tests/results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-screenshot-evidence-2026-05-28.md` | Created | Indexes retained app-flow and JSON-output screenshots. |
| `tests/results/M5-DocumentParsing-M0-M4/M5-DocumentParsing-actual-app-flow-summary-2026-05-28.json` | Created | Stores app-flow metadata using actual project test data without copying full sensitive document text into Markdown evidence. |
| `tests/results/M5-DocumentParsing-AllInputsManualUnit-2026-05-28/M5-all-inputs-manual-unit-summary-2026-05-28.md` | Created | Summarizes the all-inputs manual parser run using metadata and finding codes only. |
| `tests/results/M5-DocumentParsing-AllInputsManualUnit-2026-05-28/M5-all-inputs-manual-unit-output-2026-05-28.json` | Created | Stores the full local M5 JSON output for every approved test input file. |
| `tests/results/M5-DocumentParsing-AllInputsManualUnit-2026-05-28/M5-all-inputs-manual-unit-raw-output-2026-05-28.txt` | Created | Stores terminal-style output for the all-inputs manual parser run. |


## Testing Boundary (M13)

From M13 onward, official tests and evidence for this module run through the Docker stack:

| Tier | Where | Tool |
| --- | --- | --- |
| Unit / contract tests | Stats runtime container | `tests\scripts\regression\run_module_unit_tests.ps1` |
| Acceptance / evidence | Docker stack | `tests\scripts\regression\run_docker_full_regression_evidence.ps1` |

Host-side runs are development diagnostics only and must be superseded by container-run evidence before module acceptance.

## Verification

Official container-first diagnostic command:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_module_unit_tests.ps1
```

This runs M5 tests inside `stats-runtime` with the other module suites.

Official full regression/evidence command:

```powershell
powershell -ExecutionPolicy Bypass -File tests\scripts\regression\run_docker_full_regression_evidence.ps1
```

This runs the containerized validate -> ingest -> parse -> extract -> validate flow. Historical host-side M5 diagnostics from earlier development were superseded by the M13 container-first policy and must not be recorded as acceptance evidence.

The M5 `m7_handoff` payload remains part of the API/debug contract and evidence checks, but it is not the normal Upload page output for users.

## Current Classification Refinement Plan

- M5 classification will use shared JSON vocabulary and rules under root `config/`.
- The same classification rules apply after direct PDF text extraction, scanned-PDF OCR, and image OCR.
- M5 will return `document_type` and `document_subtype`; downstream modules preserve/use those values but do not define them.
- Runtime uploads will not mutate classification vocabulary or rules. Unknown document shapes are flagged for developer-reviewed follow-up rather than auto-added.
- Official verification for the classification refinement must run inside `stats-runtime` through the container-first test runner.

<!-- M5/M6 End -->
