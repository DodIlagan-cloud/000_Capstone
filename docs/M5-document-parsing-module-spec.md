<!-- M5 - Document Parsing Module Start -->
<!-- Specifies the merged OCR/text extraction and document classification module before implementation. -->

# Module 5 Document Parsing Module Specification

## Module Summary

Module 5 establishes the reusable **Document Parsing Module** for the Stats project. It combines the former OCR/text extraction and document classification responsibilities into one measurable parse step.

M5 receives a validation-accepted document from the File Validation and Ingestion Module, extracts usable text using the correct strategy for the file, classifies the document type, and returns parse quality, OCR readiness, redacted evidence, findings, and evaluation metadata.

This module does **not** extract final transaction rows, clean financial data, write Stats database records, render dashboards, fetch email, or own Stats Web presentation. Those concerns belong to later modules.

Implementation must not proceed until this specification is reviewed and accepted.

## Architecture Alignment

M5 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M2-stats-web-shell-spec.md`
- `docs/M3-file-validation-module-spec.md`

The corrected module boundary is:

| Field | M5 Direction |
| --- | --- |
| Build order | `5` |
| Module | Document Parsing Module |
| Type | Standalone reusable module |
| Main responsibility | Extract text from PDFs/images/scans, classify document type, and expose measurable parse metadata |
| Reusable contract | Document parsing request/result contract |
| Owner folder | `modules/document-parsing-module/` |
| Stats Web role | Calls M5 after validation/ingestion succeeds; does not implement OCR or classification logic |

## Roadmap Alignment Note

The current roadmap may still show M5 as OCR Extraction and M6 as Document Classification. That split is superseded by this spec. After this M5 spec is approved, the roadmap should be updated so:

- M5 covers Document Parsing: OCR/text extraction plus document classification.
- Former M6 classification work is merged into M5.
- Later transaction/data-quality work moves to the next module group.
- M13 starts early only as a portable runtime/tooling dependency for M5 OCR, not as full cloud deployment.

## Goals

- Provide a standalone FastAPI service for document parsing.
- Accept PDF, PNG, JPG, and JPEG documents from upload/intake workflows.
- Choose direct PDF text extraction when a PDF contains usable embedded text.
- Use Tesseract OCR when configured for image files or scanned/no-text PDFs.
- Use a PDF rendering dependency, preferably PyMuPDF, to render scanned PDF pages before OCR.
- Classify parsed documents as `bank_statement`, `receipt`, `invoice`, `utility_bill`, or `unknown`.
- Return strategy metadata explaining whether the module used PDF text extraction, OCR, disabled OCR handling, or failure handling.
- Return quality metadata such as text length, page count, pages processed, empty-page count, and low-text status.
- Return explicit findings for unsupported media, unreadable files, OCR disabled, Tesseract unavailable, renderer unavailable, OCR failure, no text, low text quality, and uncertain classification.
- Return evaluation-ready fields for measuring extraction reliability, OCR fallback rate, classification confidence, processing time, and redaction compliance.
- Redact personal information, account numbers, card numbers, and other sensitive values from evidence previews.
- Use real approved project TestData for automated/evidence checks.
- Keep runtime behavior configurable through defaults, ignored local overrides, environment variables, and later M13 container settings.

## Non-Goals

- Validating upload file type, size, extension, or signatures. That belongs to M3/M4.
- Creating ingestion records or storage handoff records. That belongs to M3/M4.
- Extracting structured transaction rows or financial fields. That belongs to Transaction Processing.
- Cleaning, categorising, deduplicating, or validating transaction records.
- Persisting parsed results into the Stats database.
- Owning dashboard/reporting views.
- Owning Stats Web UI layout beyond defining what information the caller may display.
- Creating full cloud deployment. M13/M14 own deployment packaging and cloud readiness.

## Inputs

M5 accepts document content or an allowed document reference from the workflow layer.

| Input | Required | Description |
| --- | --- | --- |
| `file` | Yes for upload endpoint | Multipart PDF/image content. |
| `ingestion_id` | No | Upstream ingestion identifier from M3/M4. |
| `source_type` | No | Source such as `manual_upload` or future `email_attachment`. |
| `source_id` | No | Caller-provided source identifier. |
| `sha256` | No | Upstream file hash for traceability. |
| `allow_direct_text` | No | Request-level override for direct PDF extraction. |
| `allow_ocr_fallback` | No | Request-level override for OCR fallback. |
| `language` | No | OCR language hint such as `eng`. |
| `page_limit` | No | Maximum pages to parse/OCR. |
| `classification_threshold` | No | Minimum confidence for non-unknown classification. |

## Outputs

M5 returns a **Document Parsing Result**.

| Output | Description |
| --- | --- |
| `parse_id` | Unique parse attempt identifier. |
| `status` | `completed`, `completed_with_warnings`, `failed`, or `unsupported`. |
| `document` | Source filename, normalized filename, size, media type, ingestion ID, source, and hash. |
| `text` | Extracted text for downstream processing. |
| `pages` | Per-page/per-image text, length, and empty-page flag. |
| `metadata` | Extraction method, OCR engine, page counts, elapsed time, language, and page limit. |
| `strategy` | Selected strategy and decision reason. |
| `classification` | Document type, confidence, classification status, and reason codes. |
| `quality` | Text length, page coverage, empty-page count, and low-text flag. |
| `evaluation` | Measurement fields for later evaluation and reporting. |
| `evidence` | Redacted text preview and redaction counts. |
| `findings` | Explicit warning/error codes and messages. |

M5 does not return final transaction records.

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service and OCR readiness metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/parses` | `POST` | Parses a multipart document and returns the Document Parsing Result. |

## Strategy Rules

| Condition | Expected Strategy |
| --- | --- |
| PDF has usable embedded text and direct text is enabled | `pdf_text` |
| PDF has insufficient/no embedded text and OCR fallback is enabled | `tesseract_ocr` after page rendering |
| PNG/JPG/JPEG and OCR fallback is enabled | `tesseract_ocr` |
| OCR is needed but disabled | `ocr_disabled` with explicit finding |
| OCR is enabled but Tesseract is unavailable | `tesseract_ocr` attempted with `TESSERACT_UNAVAILABLE` |
| Scanned PDF OCR needs rendering but renderer is unavailable | `PDF_RENDERER_UNAVAILABLE` |
| Unsupported media type | `unsupported` |

## Finding Codes

| Code | Severity | Meaning |
| --- | --- | --- |
| `MISSING_DOCUMENT` | Error | No content was supplied. |
| `DOCUMENT_TOO_LARGE` | Error | Document exceeds configured maximum size. |
| `UNSUPPORTED_MEDIA_TYPE` | Error | Media type is not supported. |
| `UNREADABLE_DOCUMENT` | Error | PDF could not be opened or parsed. |
| `DIRECT_TEXT_DISABLED` | Warning | Direct PDF text extraction is disabled. |
| `OCR_FALLBACK_DISABLED` | Warning/Error | OCR was needed but disabled. |
| `TESSERACT_UNAVAILABLE` | Error | OCR was needed but Tesseract is unavailable. |
| `PDF_RENDERER_UNAVAILABLE` | Error | Scanned PDF OCR needs rendering but renderer is unavailable. |
| `OCR_FAILED` | Error | OCR engine failed while processing the document. |
| `OCR_TIMEOUT` | Error | OCR exceeded the configured timeout. |
| `PAGE_LIMIT_APPLIED` | Warning | Only configured maximum pages were processed. |
| `LOW_TEXT_QUALITY` | Warning | Extracted text is below the configured threshold. |
| `NO_TEXT_EXTRACTED` | Warning | Parsing completed without usable text. |
| `CLASSIFICATION_UNKNOWN` | Warning | Classification confidence was below threshold. |
| `CLASSIFICATION_AMBIGUOUS` | Warning | Multiple classes were plausible. |
| `UNSUPPORTED_DOCUMENT_CLASS` | Error | No supported classes are configured. |

## Runtime Configuration

Configuration must load from committed safe defaults, optional ignored `.env`, and environment variables.

Expected settings:

| Setting | Suggested Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Document Parsing Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8015` | Local API port. |
| `CORS_ALLOWED_ORIGINS` | Stats Web local origins | Browser caller origins. |
| `SUPPORTED_MIME_TYPES` | `application/pdf,image/png,image/jpeg` | Supported input media. |
| `MAX_DOCUMENT_SIZE_BYTES` | `10485760` | Maximum accepted parse input size. |
| `ALLOW_DIRECT_TEXT` | `true` | Enables direct PDF text extraction. |
| `ALLOW_OCR_FALLBACK` | `false` locally until OCR runtime is configured | Enables Tesseract fallback. |
| `OCR_ENGINE` | `none` locally, `tesseract` in packaged runtime | OCR engine identifier. |
| `TESSERACT_CMD` | empty locally unless needed | Path to Tesseract executable. |
| `TESSDATA_PREFIX` | empty locally unless needed | Path to OCR language data. |
| `OCR_LANGUAGES` | `eng` | OCR language hint. |
| `SUPPORTED_DOCUMENT_TYPES` | `bank_statement,receipt,invoice,utility_bill,unknown` | Classification classes. |
| `CLASSIFICATION_CONFIDENCE_THRESHOLD` | `0.70` | Minimum non-unknown confidence. |
| `EXTRACTION_TIMEOUT_SECONDS` | `30` | Processing timeout. |
| `MAX_PAGE_COUNT` | `25` | Page processing limit. |
| `MIN_TEXT_LENGTH` | `20` | Low/no-text threshold. |
| `REDACT_EVIDENCE_OUTPUT` | `true` | Enables redacted preview output. |
| `REDACTION_PREVIEW_CHARS` | `500` | Maximum preview length. |

Hardcoded environment-dependent runtime values allowed in source: none.

## M13 Runtime Alignment

M5 needs Tesseract and PDF rendering support, but it must not assume those tools are manually installed on a developer laptop or cloud VM.

M13 owns the single top-level Stats runtime container that will package:

- Stats Web.
- Current module APIs.
- Python runtime/dependencies.
- Tesseract executable.
- Required OCR language data, at minimum `eng`.
- PyMuPDF or equivalent PDF renderer.
- Startup orchestration and health checks.

M5 owns OCR behavior. M13 owns portable runtime packaging.

## Stats Web Flow

The normal user flow should be seamless:

```text
drag/drop document -> validate -> ingest -> parse -> display parse result
```

Stats Web should not require a separate “parse contents” button for the normal path. After validation succeeds and ingestion returns a queued or duplicate handoff, Stats Web or the workflow coordinator should call M5 automatically.

Stats Web may display:

- parse status
- document type
- confidence
- strategy
- text length
- findings
- full M5 JSON output for evaluation/debugging

Stats Web must not implement OCR, PDF parsing, redaction, or classification rules.

## Ethical Data Handling

M5 processes financial documents and must follow ethical data handling expectations:

- Tests and evidence must use the approved TestData directory, not ad hoc synthetic substitutes, unless the user explicitly approves a narrow isolated unit fixture.
- Evidence summaries must not copy full raw extracted text from personal financial documents.
- Evidence previews must redact personal information, card numbers, account numbers, email addresses, and similar sensitive identifiers.
- Raw API responses may be viewable locally for development/evaluation, but assessment summaries should retain only metadata and redacted previews.
- Redaction counts should be included so evaluation can measure privacy controls.

## Testing Boundary (M13)

M13 establishes the required testing split for M5:

| Tier | What runs | Where | Tool |
| --- | --- | --- | --- |
| Unit / contract | Module-level checks, parse logic, OCR disabled/unavailable states | Host machine | `pytest` in `modules/document-parsing-module/` |
| Acceptance / evidence (OCR end-to-end) | Real fixture files through containerized Tesseract OCR | Docker stack | `tests\scripts\M13-Containerization\run_docker_acceptance_evidence.ps1` |

Local `pytest` remains the fast development feedback path and must not be removed. Evidence that confirms `strategy: tesseract_ocr` for image files and `method: ocr` for scanned PDFs requires the M13 containerized runtime.

## Testing

M5 tests must be efficient and scoped to touched behavior.

Module-local automated tests must cover:

- App import and metadata.
- `/health` and `/` endpoints.
- OCR readiness metadata.
- Runtime defaults and environment overrides.
- Direct PDF text extraction.
- Real configured TestData PDF parsing.
- Image OCR path when OCR is enabled.
- Scanned/no-text PDF OCR path when OCR is enabled.
- OCR disabled behavior.
- Tesseract unavailable behavior.
- PDF renderer unavailable behavior.
- Unsupported media type behavior.
- Classification for supported document types.
- Unknown/low-confidence classification.
- Redaction of sensitive evidence values.
- Evaluation metadata fields.
- Multipart `/api/v1/parses` endpoint.

Actual app evidence should cover:

- User signs in.
- Upload page accepts drag/drop or selected file.
- File validates through M3/M4.
- Accepted file is ingested.
- M5 parse runs automatically.
- UI shows parse summary and full JSON output.
- Evidence uses approved TestData.

Regression test selection:

| Condition | Regression Scope |
| --- | --- |
| M5 code/config/contract changes only | Run M5 tests plus affected M5 evidence. |
| Stats Web upload/orchestration changes | Run targeted Stats Web orchestration/build checks plus app-flow evidence. |
| M13 runtime dependency changes | Run M13 containerization contract checks. |
| Unrelated module unchanged | Do not rerun unrelated module tests. |
| Explicit end-to-end regression requested | Run full cross-module workflow evidence. |

## Acceptance Criteria

M5 is complete when:

- The approved spec exists before implementation.
- `modules/document-parsing-module/` contains the standalone runtime, configuration, README, and tests.
- `/health` exposes OCR readiness.
- `/api/v1/parses` returns the documented Document Parsing Result.
- Direct PDF text extraction works for text-layer PDFs.
- Tesseract OCR works for image inputs and scanned/no-text PDFs when configured.
- OCR-disabled and OCR-unavailable states return explicit findings.
- Classification output is included in the parse result.
- Evaluation metadata is present and measurable.
- Evidence previews are redacted.
- Stats Web can automatically validate, ingest, parse, and display full M5 JSON.
- Tests use the approved TestData directory.
- M13 runtime alignment is documented for portable Tesseract/OCR support.

## Deferred Items

- Transaction extraction and financial field structuring belong to the next transaction processing module.
- Database persistence of parse results belongs to Stats Data and Persistence.
- Full production/cloud deployment belongs to M13/M14.
- Evaluation reports and ground-truth scoring belong to M15.

<!-- M5/M6 End -->
