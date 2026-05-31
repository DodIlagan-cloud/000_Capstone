<!-- M7 - Transaction Extraction Module Start -->
<!-- Specifies the transaction candidate extraction module before implementation grows. -->

# Module 7 Transaction Extraction Module Specification

## Module Summary

Module 7 establishes the reusable **Transaction Extraction Module** for the Stats project.

M7 receives parsed text and document context from the M5 Document Parsing Module, identifies transaction-like records and document-level financial fields, and returns extraction candidates with source and confidence metadata.

This module does **not** validate, clean, deduplicate, persist, or report final financial records. Those concerns belong to M8 Data Validation, M9 Stats Data and Persistence, and M11 Dashboard and Reporting.

## Architecture Alignment

M7 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M5-document-parsing-module-spec.md`
- `contracts/extraction/README.md`
- `contracts/transactions/README.md`

| Field | M7 Direction |
| --- | --- |
| Build order | `7` |
| Module | Transaction Extraction Module |
| Type | Standalone reusable module |
| Main responsibility | Extract transaction and financial field candidates from parsed document text |
| Reusable contract | Transaction extraction request/result contract |
| Owner folder | `modules/transaction-extraction-module/` |
| Stats Web role | May call M7 after M5 parsing; must not implement transaction extraction rules |

## Goals

- Provide a standalone FastAPI service for transaction candidate extraction.
- Accept M5-style parsed text, document classification, document metadata, page text, and extraction options.
- Extract transaction candidates with date, description, amount, direction, source line, page, confidence, and reason codes.
- Extract document-level financial field candidates such as total amount due, minimum amount due, payment due date, statement date, transfer amount, and reference number.
- Return explicit findings for missing text, low-confidence extraction, unsupported document type, ambiguous amount/date, no transaction candidates, and page limit application.
- Surface M5 OCR-quality findings as input-quality warnings so poor upstream OCR is measurable without M7 rerunning Tesseract.
- Return evaluation-ready metadata for downstream testing and evidence.
- Keep runtime behavior configurable through safe defaults, ignored local overrides, and environment variables.

## Non-Goals

- OCR, direct PDF text extraction, or document classification.
- File validation, upload intake, or ingestion records.
- Cleaning or normalizing records into final ledger rows.
- Duplicate detection across records or documents.
- Persisting extraction results into the Stats database.
- Rendering dashboards or reports.
- Email retrieval.
- Cloud deployment.

## Inputs

M7 accepts a JSON extraction request.

| Input | Required | Description |
| --- | --- | --- |
| `parse_id` | No | Upstream M5 parse attempt identifier. |
| `document` | No | Source filename, hash, ingestion ID, and source context. |
| `document_type` | No | M5 document classification, such as `bank_statement`, `receipt`, `invoice`, `utility_bill`, or `unknown`. |
| `classification_confidence` | No | M5 classification confidence. |
| `classification` | No | Full M5 classification object. M7 may derive `document_type` from this when no top-level override is supplied. |
| `text` | Yes | Full extracted text from M5. |
| `pages` | No | Per-page text blocks from M5. |
| `metadata` | No | Parse/extraction metadata from M5. |
| `quality` | No | M5 parse quality metadata, including low-text and page coverage signals. |
| `findings` | No | M5 parse findings. M7 uses these as input-quality context, not as a reason to rerun OCR. |
| `options` | No | Extraction thresholds, document type overrides, page limits, and feature switches. |

## Outputs

M7 returns a **Transaction Extraction Result**.

| Output | Description |
| --- | --- |
| `extraction_id` | Unique extraction attempt identifier. |
| `status` | `completed`, `completed_with_warnings`, `failed`, or `unsupported`. |
| `parse_id` | Upstream M5 parse identifier when supplied. |
| `document` | Source document trace metadata. |
| `transaction_candidates` | Candidate transaction rows with source/confidence metadata. |
| `financial_field_candidates` | Candidate document-level fields with source/confidence metadata. |
| `summary` | Candidate counts, amount totals, and coverage metadata. |
| `evaluation` | Measurement fields for later evaluation and reporting. |
| `findings` | Explicit warning/error codes and messages. |

M7 does not return final validated transaction records.

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/extractions` | `POST` | Extracts transaction and financial field candidates from parsed text. |

## Extraction Strategy

M7 starts with deterministic rules so results are explainable and testable:

- Split parsed text into source lines and retain line numbers.
- Detect financial amounts with configurable currency and decimal rules.
- Detect dates in common statement, receipt, invoice, and transfer formats.
- Use document-type hints to prioritize patterns:
  - `bank_statement`: transaction rows, statement date, payment due date, balances, total amount due.
  - `receipt`: merchant/transfer amount/reference/confirmation style fields.
  - `invoice` and `utility_bill`: due date, total due, invoice/reference number.
  - `unknown`: conservative candidate extraction with lower confidence and findings when uncertain.
- Return candidates rather than final records when a line has partial but plausible transaction data.

Future implementation may add templates or model-assisted extraction behind configuration, but deterministic behavior is the initial acceptance boundary.

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_TEXT` | Error | No parsed text was supplied. |
| `UNSUPPORTED_DOCUMENT_TYPE` | Warning | The supplied document type is not configured for extraction. |
| `NO_TRANSACTION_CANDIDATES` | Warning | No transaction-like rows were found. |
| `NO_FINANCIAL_FIELDS` | Warning | No document-level financial fields were found. |
| `LOW_CONFIDENCE_EXTRACTION` | Warning | Extracted candidates are below the configured confidence threshold. |
| `AMBIGUOUS_AMOUNT` | Warning | Multiple amounts on a source line make direction or value uncertain. |
| `AMBIGUOUS_DATE` | Warning | Date text was detected but could not be normalized confidently. |
| `PAGE_LIMIT_APPLIED` | Warning | Only configured pages were processed. |
| `TEXT_TRUNCATED` | Warning | Input text was truncated by configured processing limits. |
| `LOW_TEXT_QUALITY_INPUT` | Warning | M5 reported low extracted text quality. |
| `UPSTREAM_NO_TEXT_EXTRACTED` | Warning | M5 reported no usable extracted text. |
| `UPSTREAM_OCR_DISABLED` | Warning | M5 reported OCR was needed but disabled. |
| `UPSTREAM_OCR_FAILURE` | Warning | M5 reported Tesseract, renderer, or OCR processing failure. |
| `UPSTREAM_OCR_QUALITY_WEAK` | Warning | M5 reported low OCR confidence or noisy OCR text. |

## Runtime Configuration

Configuration must load from committed safe defaults, optional ignored `.env`, and environment variables.

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Transaction Extraction Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8016` | Container-internal API port. |
| `CORS_ALLOWED_ORIGINS` | Stats Web local origins | Browser caller origins. |
| `SUPPORTED_DOCUMENT_TYPES` | `bank_statement,receipt,invoice,utility_bill,unknown` | Supported M5 classifications. |
| `DEFAULT_CURRENCY` | `PHP` | Currency assigned when text does not identify one. |
| `MIN_TRANSACTION_CONFIDENCE` | `0.55` | Minimum candidate confidence before warning. |
| `MAX_TEXT_CHARS` | `100000` | Maximum text processed in one request. |
| `MAX_PAGE_COUNT` | `25` | Maximum page blocks processed. |

<!-- M13 - Containerization Start -->
M13 update: `API_PORT=8016` is the container-internal Transaction Extraction API port for official tests and runtime evidence.
<!-- M13 End -->
| `ENABLE_FIELD_EXTRACTION` | `true` | Enables document-level field candidate extraction. |
| `ENABLE_TRANSACTION_ROWS` | `true` | Enables row-level transaction candidate extraction. |

Hardcoded environment-dependent runtime values allowed in source: none.

## Testing

Module-local automated tests must cover:

- App import and metadata.
- `/health` and `/` endpoints.
- Runtime defaults and environment overrides.
- Missing text behavior.
- Bank statement transaction candidate extraction.
- Receipt/proof-of-payment field extraction.
- Invoice/bill due date and total field extraction.
- Unknown document handling.
- Ambiguous amount/date findings.
- M5-shaped input with `classification`, `quality`, `metadata`, `pages`, and parse `findings`.
- M5 low-text/OCR findings converted into M7 input-quality findings.
- M5 OCR-quality findings, including low confidence and noisy text, converted into M7 input-quality findings.
- Evaluation metadata fields.
- Multipart-free JSON `/api/v1/extractions` endpoint.

Regression test selection:

| Condition | Regression Scope |
| --- | --- |
| M7 code/config/contract changes only | Run M7 tests inside `stats-runtime` plus affected container contract checks. |
| M5 parse result shape changes | Run M5 and M7 contract tests inside `stats-runtime`. |
| Stats Web orchestration changes | Run Stats Web orchestration/build checks inside `stats-runtime` plus affected container app-flow evidence. |
| M13 runtime changes | Run M13 containerization contract and Docker acceptance checks. |

## Acceptance Criteria

M7 is complete when:

- The approved spec exists before implementation grows.
- `modules/transaction-extraction-module/` contains standalone runtime, configuration, README, and tests.
- `/health` and `/api/v1/extractions` are available.
- M5-style parsed text can be submitted as JSON.
- M5 classification and quality fields are accepted directly without rerunning OCR.
- M5 low/no-text and OCR readiness findings are surfaced as M7 input-quality findings.
- Transaction candidates include date/description/amount/source/confidence metadata where available.
- Financial field candidates include field name/value/source/confidence metadata where available.
- Missing/ambiguous/unsupported cases return explicit findings.
- Evaluation metadata is present and measurable.
<!-- M13 - Containerization Start -->
- Unit tests pass inside the `stats-runtime` container through `tests\scripts\regression\run_module_unit_tests.ps1`.
<!-- M13 End -->
- M7 remains free of Stats persistence, dashboard, and M8 validation logic.

## Deferred Items

- Record normalization, cleaning, duplicate checks, and validation belong to M8.
- Database persistence belongs to M9.
- Full workflow orchestration belongs to M10.
- Dashboard/reporting belongs to M11.
- Email attachment retrieval belongs to M12.
- Container and cloud deployment updates belong to M13/M14.

<!-- M7 End -->
