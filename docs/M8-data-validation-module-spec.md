<!-- M8 - Data Validation Module Start -->
<!-- Specifies the data validation module before implementation grows. -->

# Module 8 Data Validation Module Specification

## Module Summary

Module 8 establishes the reusable **Data Validation Module** for the Stats project.

M8 receives transaction and financial field candidates from M7, cleans candidate values, validates required fields, detects duplicate records within the supplied validation request, and returns normalized records with data-quality findings.

This module does **not** extract transactions, rerun OCR, classify documents, persist records, or render dashboards. Those concerns belong to M5, M7, M9, and M11.

## Architecture Alignment

| Field | M8 Direction |
| --- | --- |
| Build order | `8` |
| Module | Data Validation Module |
| Type | Standalone reusable module |
| Main responsibility | Clean, validate, warn, and detect duplicates/incomplete transaction records |
| Reusable contract | Data-quality report contract |
| Owner folder | `modules/data-validation-module/` |
| Stats Web role | May call M8 after M7 extraction; must not implement validation rules |

## Goals

- Provide a standalone FastAPI service for validating M7 candidates.
- Accept M7-shaped transaction and financial field candidates as JSON.
- Normalize transaction dates, descriptions, currencies, directions, and signed amounts.
- Flag missing date, missing description, invalid amount, unknown direction, and low confidence.
- Detect duplicate transaction records within the supplied validation batch using deterministic date, description, amount, currency, and direction keys.
- Keep database-backed duplicate checks out of M8; M9/M10 will compare normalized records against stored transactions before persistence.
- Return summary and evaluation metadata for module evidence.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.
- Follow the central Stats path convention if file-based fixtures or evidence paths are added: resolve logical paths from `config/stats.paths.json` and `STATS_APP_ROOT` instead of assuming a local, container, or cloud root.

## Non-Goals

- OCR, parsing, document classification, or transaction extraction.
- Stats database writes, migrations, or persistence adapters.
- Dashboard/report rendering.
- Cross-document or database-backed historical reconciliation beyond supplied candidates.
- Email retrieval or cloud deployment.

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/validations` | `POST` | Validates and normalizes transaction candidates. |

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_CANDIDATES` | Error | No transaction or financial field candidates were supplied. |
| `MISSING_TRANSACTION_DATE` | Warning | A transaction candidate lacks a usable date. |
| `MISSING_DESCRIPTION` | Warning | A transaction candidate lacks a usable description. |
| `INVALID_AMOUNT` | Warning | A transaction amount is zero or negative after cleaning. |
| `UNKNOWN_DIRECTION` | Warning | Debit/credit direction is missing or unknown. |
| `LOW_CONFIDENCE_RECORD` | Warning | Candidate confidence is below the configured validation threshold. |
| `LOW_CONFIDENCE_FIELD` | Warning | Financial field confidence is below the configured validation threshold. |
| `MISSING_FIELD_VALUE` | Warning | A financial field has no usable value. |
| `DUPLICATE_TRANSACTION` | Warning | A normalized transaction duplicates an earlier normalized record in the same validation batch. |
| `RECORD_LIMIT_APPLIED` | Warning | Only the configured maximum records were validated. |

## Runtime Configuration

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Data Validation Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8017` | Container-internal API port. |
| `DEFAULT_CURRENCY` | `PHP` | Currency assigned when M7 omitted one. |
| `MIN_RECORD_CONFIDENCE` | `0.65` | Minimum confidence before warning. |
| `DUPLICATE_MATCH_AMOUNT_TOLERANCE` | `0.01` | Duplicate amount comparison tolerance. |
| `REQUIRE_TRANSACTION_DATE` | `true` | Whether missing dates produce warnings. |
| `REQUIRE_TRANSACTION_DIRECTION` | `true` | Whether unknown direction produces warnings. |

<!-- M13 - Containerization Start -->
M13 update: `API_PORT=8017` is the container-internal Data Validation API port for official tests and runtime evidence.
<!-- M13 End -->
| `ENABLE_DUPLICATE_DETECTION` | `true` | Enables duplicate detection. |
| `MAX_RECORDS_PER_REQUEST` | `1000` | Maximum transaction candidates processed. |

Duplicate detection in M8 is intentionally request-local. It compares records in the current validation payload only and does not query the Stats database or any persistence store.

M8 has no durable file-storage responsibility. If future validation evidence or fixture locations are configured, they must use `config/stats.paths.json`, `STATS_APP_ROOT`, and the root `tests/` tree rather than module-local or machine-specific paths.

## Acceptance Criteria

- The approved spec exists before implementation grows.
- `modules/data-validation-module/` contains standalone runtime, configuration, README, and tests.
- `/health` and `/api/v1/validations` are available.
- M7-shaped extraction results can be submitted as JSON.
- Normalized records include date, description, amount, currency, direction, signed amount, source, confidence, and quality status.
- Same-batch duplicate, incomplete, invalid, and low-confidence records return explicit findings.
- Evaluation metadata is present and measurable.
- Unit tests pass inside the M13 Stats runtime container through the official container runner.
- M8 remains free of Stats persistence, database duplicate checks, and dashboard logic.

## Stats Web Upload Checkpoint

Stats Web should present M8 results as a user-facing **transaction check results** checkpoint, not as raw module JSON.

The normal Upload page should show:

- Processing steps in plain language: file accepted, document uploaded, text read, transactions checked.
- A transaction summary: transactions found, ready to save, needs review, and saved count when persistence exists.
- A needs-review callout when M8 returns warnings or invalid records.
- A concise transaction preview table with date, description, amount, and status.
- A short document summary with filename, detected document type, text-read status, and processing result.
- Clear next actions: save ready transactions, review transactions, upload another document.

The normal Upload page should not show:

- Raw M5 parse JSON.
<!-- M8 - Data Validation Module Start -->
- Raw M5/M7/M8 JSON shown as developer details only, not as the main upload result.
<!-- M8 End -->
- Internal module names as the main user-facing status.
- Parse IDs, extraction IDs, hashes, OCR engine names, confidence decimals, or source debug fields unless a developer/admin detail view is explicitly opened.

Before M9 exists, the primary save action may remain disabled or labelled as a deferred storage step. After M9/M10 exist, clicking the primary save action should send M8 normalized records to persistence, where database duplicate checks are performed.

## Testing Boundary

From M13 onward, M8 official verification must run through the Stats container runtime.

| Test Type | Required Execution |
| --- | --- |
| M8 unit/API tests | Inside `stats-runtime` via `tests\scripts\regression\run_module_unit_tests.ps1` |
| Stats Web upload checkpoint verification | Against the container-exposed Stats Web entry point on `http://127.0.0.1:8080` |
| Runtime packaging checks | Through Docker build/start of `stats-runtime` |

Host-side commands are development diagnostics only and must not be recorded as M8 acceptance evidence.

<!-- M8 End -->
