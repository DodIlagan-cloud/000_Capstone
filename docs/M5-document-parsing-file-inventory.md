<!-- M5 - Document Parsing Module Start -->
<!-- Documents planned and completed files for the M5 Document Parsing Module. -->

# M5 Document Parsing File Inventory

## Summary

This document lists the files planned, created, or modified for **M5 Document Parsing**. It must be created with the M5 specification before implementation begins so module scope, file ownership, and evidence expectations are visible from the start.

Current status: **implementation pass complete** for the M5 module runtime, Stats Web upload flow integration, targeted regression checks, and the M7-aligned OCR quality improvement pass. M13 containerization is now the official runtime and testing path for portable OCR tooling and module evidence.

## Specification and Contracts

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Created/Modified | Defines M5 goals, boundaries, runtime configuration, API contract, OCR strategy rules, classification output, redaction, testing, M13 runtime alignment, and acceptance criteria. Updated on 2026-06-13 to make reviewed MVP manual Upload document classification a human-confirmation path and reserve admin pending suggestions for post-MVP automated/email workflows and broader governance. |
| `docs/M5-document-parsing-file-inventory.md` | Created | Documents planned and completed files for M5. |
| `docs/M5-document-parsing-activity-flow.md` | Created | Provides the printable swimlane activity flow diagram for the merged M5 parsing, OCR, classification, redaction, and extraction handoff behavior. |
| `docs/module-test-flow-playbook.md` | Created | Defines the planning-only module test-flow checklist for M0-M14, including the refined M5/M6 parse/OCR/classification evidence flow. Updating this file does not mean tests were executed. |
| `docs/building-block-module-plan.md` | Modified | Aligns the roadmap so M5 is the merged Document Parsing module and former M6 classification is included in M5. |
| `docs/building-block-module-io-map.md` | Modified | Defines the M5 input/output contract from file intake to transaction processing. |
| `contracts/extraction/README.md` | Modified | Adds the concrete M5 Document Parsing request/result contract summary. |
| `contracts/document-classification/README.md` | Created | Defines shared classification vocabulary ownership, module responsibilities, update lifecycle, and the developer-maintained limitation for unknown document shapes. |
| `config/document-classification.vocabulary.json` | Deprecated for runtime use | Historical machine-readable document type/subtype vocabulary. It may be used only as migration seed/reference material after the 2026-06-10 M9 recognition-settings decision. |
| `config/document-classification.rules.json` | Deprecated for runtime use | Historical generic text-signal rules. It may be used only as migration seed/reference material after the 2026-06-10 M9 recognition-settings decision. |
| `.dockerignore` | Modified | Keeps real `tests/input` source files out of the Docker build context; container-first evidence runners copy approved local fixtures into the running container explicitly. |

## Standalone Module

| File | Change Type | Description |
| --- | --- | --- |
| `modules/document-parsing-module/README.md` | Created | Documents local runtime, tests, configuration, OCR dependency behavior, and module boundary. |
| `modules/document-parsing-module/requirements.txt` | Created | Lists FastAPI, PDF parsing, OCR adapter, PDF rendering, config, and test dependencies. |
| `modules/document-parsing-module/config/defaults.env` | Created/Modified | Provides safe committed defaults for local parsing runtime settings, including OCR PSM retry, adaptive scanned-PDF fast-pass thresholds, image OCR early-stop thresholds, render scale, quality thresholds, and disabled-by-default Gemini AI-assisted classification settings. |
| `modules/document-parsing-module/.env.example` | Created | Provides local override examples for OCR, Tesseract, test data, and runtime ports. |
| `modules/document-parsing-module/app/main.py` | Created | Starts the Document Parsing API. |
| `modules/document-parsing-module/app/config.py` | Created/Modified | Loads runtime settings from defaults, optional local overrides, and environment variables, including OCR retry, adaptive scanned-PDF fast-pass, image OCR early-stop, render-scale, quality scoring settings, optional AI-assisted classification configuration, and the planned M9 recognition settings API URL/cache settings. |
| `modules/document-parsing-module/app/models/common.py` | Created | Defines health, root metadata, and OCR readiness schemas. |
| `modules/document-parsing-module/app/models/parsing.py` | Created/Modified | Defines parsing response, classification with document type/subtype, classification source, optional AI model/confidence/review metadata, quality, evidence, findings, evaluation schemas, OCR quality metadata, OCR word-block layout evidence, image OCR early-stop metadata, receipt amount-coherence metadata, and the extraction handoff audit schema. |
| `modules/document-parsing-module/app/routes/health.py` | Created | Provides health and root endpoints. |
| `modules/document-parsing-module/app/routes/parsing.py` | Created | Provides the document parsing upload endpoint. |
| `modules/document-parsing-module/app/services/parsing_service.py` | Created/Modified | Implements PDF text extraction, OCR fallback, scanned PDF rendering, EXIF orientation handling, image preprocessing, orientation/PSM retry, OCR word-block capture, OCR quality scoring, findings, evaluation metadata, transaction-signal counting, classification-source propagation, and extraction-readiness audit output. Receipt-photo hardening adds generic autocontrast, sharpened contrast, thresholded OCR attempts, and conservative document-crop OCR variants, then scores transaction-critical receipt evidence such as date/time, EFTPOS/terminal, approval/reference, and amount/currency tokens so faint thermal-printer rows are less likely to be dropped. Cloud-dev performance hardening adds adaptive scanned-PDF OCR effort and image OCR early-stop: M5 tries prioritized OCR candidates first and escalates to broader repair attempts only when the first useful candidate is weak. Receipt amount-coherence hardening prevents early-stop when labelled amount evidence is damaged, split, or conflicting, and exposes the decision in metadata. |
<!-- M5 Recognition Settings DB Source Start - 2026-06-10 -->
| `modules/document-parsing-module/app/services/classification_service.py` | Created/Modified | Implements document type/subtype classification for both direct PDF text and Tesseract OCR output, including receipt-favored ambiguity handling for OCR retail tax invoices with terminal/payment evidence and rule-first orchestration of the optional AI-assisted fallback. Updated to load active approved vocabulary/rules from M9 and return a controlled unavailable-settings review state instead of falling back to stale committed JSON. |
| `modules/document-parsing-module/app/services/ai_classification_service.py` | Created/Modified | Implements the optional M5 AI-assisted document classification fallback, including native Gemini `generateContent` support and OpenAI-compatible support. The service is disabled by default, redacts/truncates extracted text before provider calls, sends active M9 document recognition context to the provider, records model/confidence/vocabulary-status metadata, and preserves deterministic rule results when AI confidence is low or conflicts. |
<!-- M5 Document Suggestion Approval Start - 2026-06-11 -->
| `modules/document-parsing-module/app/models/parsing.py` | Modified | Carries AI-proposed document type/subtype plus review/confirmation metadata so MVP manual Upload can confirm the classification during save while automated/email flows can still create admin-governed suggestions. |
| `modules/document-parsing-module/app/services/classification_service.py` | Modified | Loads the active M9 recognition context before AI fallback, stamps recognition-context version metadata, and keeps new AI document labels as reviewable suggestions for manual Upload confirmation or post-MVP admin governance. |
| `modules/document-parsing-module/app/services/ai_classification_service.py` | Modified | Allows AI to propose inactive/new document labels after seeing the active recognition context and returns vocabulary-status metadata for downstream review routing. |
<!-- M5 Document Suggestion Approval End - 2026-06-11 -->
| `modules/document-parsing-module/app/services/redaction_service.py` | Created | Implements evidence redaction helpers for ethical data handling. |

## Stats Web Integration Surface

| File | Change Type | Description |
| --- | --- | --- |
| `apps/stats-web/appsettings.json` | Modified | Adds configured container-internal downstream API base URLs and keeps host-side local orchestration disabled by default. |
| `apps/stats-web/Program.cs` | Modified | Adds document parsing, transaction extraction, and data validation downstream configuration. |
| `apps/stats-web/Pages/Upload.cshtml` | Modified | Displays a user-facing transaction check result after M8 validation while keeping raw M5/M7/M8 details behind developer details. |
| `apps/stats-web/Pages/Upload.cshtml.cs` | Modified | Exposes the configured parsing API base URL to the upload page. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml` | Created/Modified | Displays administrator recognition settings. Updated to read and manage active document labels/rules from M9 rather than committed JSON, including editable document recognition rules. |
| `apps/stats-web/Pages/Admin/Classifications.cshtml.cs` | Created/Modified | Backend handler for administrator recognition settings. Updated to use M9 recognition settings APIs for document label/rule add, edit, delete/deactivate workflows and removed legacy JSON-file mutation helpers. |
| `apps/stats-web/wwwroot/js/upload.js` | Modified | Runs validate -> ingest -> parse -> extract -> validate automatically and renders M8 transaction check results, including M5 subtype labels, with raw details hidden behind developer details. Cloud-dev hardening requires this flow to move to an async processing-job pattern so browser uploads poll progress instead of waiting on the synchronous M5 `/api/v1/parses` request; the async path must not force the old `page_limit=1` timeout workaround. Processing-step timing is displayed through job progress and stored through M9 rather than local JSON files. |
| `apps/stats-web/wwwroot/js/classifications.js` | Created | Enforces admin-only access and tab behavior for the classification management page that displays M5-owned document classification configuration. |
| `tests/scripts/regression/cleanup_m5_m7_m9_recognition_evidence_data_2026_06_11.py` | Created | Removes prior M5/M7/M9 recognition evidence residue so future M5 document-suggestion tests start from a production-like baseline. |
| `apps/stats-web/wwwroot/css/access.css` | Modified | Styles parse result and JSON output states. |
| `tests/integration/test_stats_web_orchestration_config.py` | Modified | Verifies Stats Web uses container-first downstream endpoints and keeps host-side process startup disabled by default. |
| `modules/file-validation-module/app/routes/ingestions.py` | Created | Restores the File Intake ingestion API surface required by the seamless validate -> ingest -> parse flow. |
| `modules/file-validation-module/app/services/ingestion_service.py` | Modified | Creates accepted-file ingestion records and converts storage-provider runtime failures into controlled rejected ingestion records/finding details before M5 parsing is invoked. |
| `apps/stats-data/migrations/azure-sql/007_document_processing_steps.sql` | Created | Adds the durable M9 timing table that stores the M5 document-parsing step duration and safe parse/OCR metadata for upload jobs. |
| `apps/stats-data/src/stats_data/processing_jobs.py` | Modified | Adds processing-step persistence helpers used by Stats Web to store M5 timing without M5 directly depending on M9. |

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
| `tests/unit/document_parsing_module/test_parsing_service.py` | Created/Modified | Verifies PDF text extraction, real `tests/input` OCR paths, unavailable dependency behavior, M9-backed vocabulary/rule classification, unavailable recognition-settings behavior with no stale JSON fallback, disabled-by-default AI classification, Gemini request redaction and response parsing, AI acceptance for weak rule results, AI/rule conflict review behavior, redaction, evaluation fields, orientation retry findings, OCR quality metadata, OCR retail receipt classification, low-contrast thermal receipt date/amount preservation, image OCR early-stop behavior, receipt amount-coherence behavior, conservative document-crop variant behavior, and extraction handoff audit readiness/redaction. OCR behavior tests must use approved input fixtures rather than generated files or mocked OCR text. |
<!-- M5 Recognition Settings DB Source End - 2026-06-10 -->
| `config/stats.runtime.json` | Modified | Registers adaptive OCR and optional AI-assisted classification settings so cloud/container runtime changes are explicit configuration instead of hidden code literals. |
| `infrastructure/cloud/azure-container-apps.env.example` | Modified | Documents the cloud-dev OCR tuning variables used to keep parsing lightweight without increasing Container App memory. |
| `tests/unit/document_parsing_module/test_parsing_api.py` | Created/Modified | Verifies the multipart parsing API, trace metadata behavior, and extraction handoff audit fields. |
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

The M5 `extraction_handoff` payload remains part of the API/debug contract and evidence checks, but it is not the normal Upload page output for users.

## Current Classification Refinement Plan

- M5 classification will use active approved vocabulary and rules from M9 recognition settings.
- The same classification rules apply after direct PDF text extraction, scanned-PDF OCR, and image OCR.
- M5 will return `document_type` and `document_subtype`; downstream modules preserve/use those values but do not define them.
- M5 will expose `classification_source`, optional AI model/version/confidence, and review reason metadata so M11/M15 can measure classification coverage without owning classification logic.
- Runtime parsing does not mutate active classification vocabulary or rules directly. In the MVP manual Upload flow, reviewed accept/save is the human-confirmation path and M9 activates accepted new document labels during save. In post-MVP email ingestion, automated workflows, or unreviewed flows, unknown document shapes become pending M9 suggestions until an administrator approves, edits, rejects, merges, or renames them.
- Committed classification JSON is deprecated for runtime use and must not be used as a stale fallback inside the container or cloud image.
- Official verification for the classification refinement must run inside `stats-runtime` through the container-first test runner.

<!-- M5 Recognition Approval Evidence Update Start - 2026-06-11 -->

## Recognition Approval Evidence Update

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Modified | Historical 2026-06-11 update required deterministic pending document suggestions when strong content evidence matches a supported document shape whose approved label is inactive. Superseded for MVP manual Upload by the 2026-06-13 user-confirmed save path; still relevant for post-MVP automated/email workflows. |
| `modules/document-parsing-module/app/services/classification_service.py` | Modified | Adds a conservative content-based receipt-shape suggestion path for unknown or ambiguous OCR classifications so M9/admin approval can restore inactive document labels in unreviewed automated/email workflows without an external AI call. |
| `tests/results/M5-M7-M9-RecognitionApproval/M5-M7-M9-recognition-approval-2026-06-11-20260611-130431/` | Created | Historical desktop evidence set proving real-JPEG OCR upload, pending document/transaction/spending suggestions, admin approval, Azure SQL updates, and post-approval management-page visibility before the MVP manual Upload user-confirmed save path was clarified. |

<!-- M5 Recognition Approval Evidence Update End - 2026-06-11 -->

<!-- M5 Recognition Resilience Update Start - 2026-06-12 -->

## Recognition Resilience Update

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Modified | Requires M5 to use a successful prior M9 in-memory settings cache during temporary M9/API outages while still prohibiting deprecated committed JSON fallback. |
| `modules/document-parsing-module/app/services/classification_service.py` | Modified | Returns the stale active-settings cache when the M9 recognition settings API is temporarily unavailable after a successful prior load. |
| `tests/unit/document_parsing_module/test_classification_hardening.py` | Created | Verifies document classification settings loading uses the prior M9 cache during a temporary outage. |

<!-- M5 Recognition Resilience Update End - 2026-06-12 -->

<!-- M5 Slug Signal Matching Update Start - 2026-06-15 -->

## Slug Signal Matching Update

| File | Change Type | Description |
| --- | --- | --- |
| `docs/M5-document-parsing-module-spec.md` | Modified | Requires M5 to match canonical M9 slug signals such as `payment_due_date` against equivalent document phrase text such as `payment due date`, and adds statement-vs-receipt regression expectations for statement-like PDFs. |
| `docs/module-test-flow-playbook.md` | Modified | Adds M5/M6 PDF statement regression proof to the planned flow without executing evidence. |
| `modules/document-parsing-module/app/services/classification_service.py` | Modified | Normalizes M9 rule signals into equivalent slug and phrase token patterns for required anchors and weighted signals while preserving canonical diagnostics. |
| `tests/unit/document_parsing_module/test_parsing_service.py` | Modified | Covers slug-style M9 document signals matching phrase text and statement summary evidence preventing confident receipt classification. |
| `tests/results/M5-M7-PdfExtractionComparison-2026-06-15/` | Diagnostic | Development diagnostic evidence that identified statement PDFs being misclassified as receipts after M9 slug-style settings were loaded. It is not acceptance evidence. |

<!-- M5 Slug Signal Matching Update End - 2026-06-15 -->

<!-- M5/M6 End -->
