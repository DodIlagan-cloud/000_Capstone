<!-- M3 - File Validation Module Start -->
<!-- Specifies the merged reusable File Validation and Ingestion Module. -->

# Module 3/4 File Validation and Ingestion Module Specification

## Module Summary

Module 3 establishes a standalone reusable File Validation Module for candidate documents entering the Stats processing workflow. After the M4 merge, the same runtime also owns accepted-file ingestion, source context, idempotency hints, configured storage handoff references, and ingestion status lookup.

This module does not perform OCR, classify documents, extract transactions, validate financial data, or update Stats-specific persistence. Those concerns belong to later modules.

## Architecture Alignment

M3 is aligned with:

- `docs/building-block-module-plan.md`
- `docs/building-block-module-io-map.md`
- `docs/M0-foundation-module-spec.md`
- `docs/M2-stats-web-shell-spec.md`

The building-block plan defines this module as:

| Field | M3 Direction |
| --- | --- |
| Build order | `3` |
| Module | File Validation and Ingestion Module |
| Type | Standalone module |
| Main responsibility | Validate file type, size, extension, signatures, hashes, rejection reasons, and create ingestion handoff records |
| Reusable contract | File validation request/result API and ingestion status contract |
| Owner folder | `modules/file-validation-module/` |

## Goals

- Provide a standalone API for validating uploaded file candidates.
- Support automatic validation when a caller selects or receives a file.
- Keep validation rules configurable without source-code edits.
- Detect supported content signatures for PDF, PNG, and JPEG files.
- Reject empty, oversized, unsupported, and mismatched files with explicit finding codes.
- Return normalized file metadata and optional SHA-256 hashes.
- Create ingestion records for validation-accepted files.
- Store accepted intake content under the configured `STORAGE_ROOT`.
- Return normalized document handoff metadata for downstream OCR.
- Expose ingestion status lookup.
- Keep the module reusable outside the Stats Web UI.
- Provide module-local automated tests.

## Non-Goals

- Duplicate-file business workflow decisions.
- OCR or text extraction.
- Document classification.
- Transaction extraction.
- Data cleaning or financial validation.
- Stats Web UI behavior.
- Stats database persistence.

## Runtime Configuration

Configuration is loaded from `config/defaults.env`, optional `.env`, and environment variables.

| Setting | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `File Validation Module` | API display name. |
| `APP_VERSION` | `1.0.0` | API version metadata. |
| `API_PREFIX` | `/api/v1` | Versioned API route prefix. |
| `API_HOST` | `127.0.0.1` | Local host binding. |
| `API_PORT` | `8014` | Local API port. |
| `CORS_ALLOWED_ORIGINS` | Stats Web local origins | Browser caller origins. |
| `MAX_FILE_SIZE_BYTES` | `10485760` | Default maximum accepted file size. |
| `ALLOWED_EXTENSIONS` | `.pdf,.png,.jpg,.jpeg` | Default allowed extensions. |
| `ALLOWED_MIME_TYPES` | `application/pdf,image/png,image/jpeg` | Default allowed detected MIME types. |
| `REQUIRE_KNOWN_SIGNATURE` | `true` | Reject files whose signatures are not recognized. |
| `COMPUTE_SHA256` | `true` | Include SHA-256 hash in validation metadata. |
| `STORAGE_ROOT` | Configured in `config/defaults.env` | Stats-owned folder for accepted intake content. |
| `DEFAULT_WORKFLOW` | `document-processing` | Workflow name used when the caller does not provide one. |
| `MAX_STORED_FILE_SIZE_BYTES` | `10485760` | Default maximum file size stored by ingestion. |

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service health metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/files/validate` | `POST` | Validates a multipart uploaded file candidate against default or request policy. |
| `/api/v1/ingestions` | `POST` | Creates an ingestion record for a validation-accepted file. |
| `/api/v1/ingestions/{ingestion_id}` | `GET` | Returns ingestion status and handoff metadata. |

`POST /api/v1/files/validate` accepts:

- `file`: multipart file content.
- `allowed_extensions`: optional comma-separated policy override.
- `allowed_mime_types`: optional comma-separated policy override.
- `max_size_bytes`: optional policy override.
- `require_known_signature`: optional policy override.
- `compute_sha256`: optional policy override.

The response includes:

- `status`: `accepted` or `rejected`.
- `metadata`: filename, normalized filename, extension, size, provided content type, detected type, and optional hash.
- `findings`: explicit warning or error codes with messages.
- `policy`: the applied validation policy.

## Finding Codes

Validation findings:

| Code | Severity | Meaning |
| --- | --- | --- |
| `EMPTY_FILE` | Error | File content has zero bytes. |
| `FILE_TOO_LARGE` | Error | File exceeds the configured maximum size. |
| `MISSING_EXTENSION` | Error | Filename has no extension. |
| `UNSUPPORTED_EXTENSION` | Error | Extension is not allowed by policy. |
| `UNKNOWN_SIGNATURE` | Error | File signature is not a supported type. |
| `UNSUPPORTED_TYPE` | Error | Detected type is not allowed by policy. |
| `SIGNATURE_EXTENSION_MISMATCH` | Error | File extension does not match detected signature. |
| `CONTENT_TYPE_MISMATCH` | Warning | Browser-provided content type differs from detected signature. |

Ingestion findings:

| Code | Severity | Meaning |
| --- | --- | --- |
| `VALIDATION_NOT_ACCEPTED` | Error | The caller submitted a file whose validation result was not accepted. |
| `EMPTY_FILE` | Error | Ingestion content has zero bytes. |
| `FILE_TOO_LARGE` | Error | File exceeds the configured ingestion storage limit. |
| `DUPLICATE_SUBMISSION` | Warning | A record already exists for the idempotency key or file hash. |

## Testing

Module-local tests must cover:

- API startup and health metadata.
- Configured defaults.
- Valid PDF acceptance.
- Empty file rejection.
- Oversized file rejection.
- Extension/content mismatch rejection.
- Unsupported file type rejection.
- API-level request policy overrides.
- Valid manual upload ingestion handoff.
- Status lookup for a created ingestion record.
- Rejection when validation status is not accepted.
- Duplicate/idempotent submission behavior.
- Config-driven real PDF automated/evidence tests using `STATS_TESTDATA_DIR`, verifying validation, ingestion, status lookup, and saved handoff under configured `STORAGE_ROOT`.
- Stats Web automatic validation on file selection, with rejected files showing findings and accepted files becoming eligible for the next parsing/ingestion step.

## Acceptance Criteria

M3 is complete when:

- `modules/file-validation-module/` contains the standalone runtime, configuration, README, and tests.
- The module exposes health/root endpoints, the versioned validation endpoint, and versioned ingestion endpoints.
- Validation results include explicit status, metadata, findings, and applied policy.
- Ingestion responses include explicit status, source context, validation summary, handoff metadata, and findings.
- The expected UI behavior is automatic validation on file selection: rejected files show findings, accepted files are prepared for the next parsing/ingestion step.
- Runtime limits, allowed policy values, workflow defaults, and storage path are configurable.
- Real PDF automated/evidence tests pass when `STATS_TESTDATA_DIR` points to the shared real application test-data directory, and fail with a clear setup message when that variable is unavailable.
- Module tests pass inside the M13 Stats runtime container.
- Contracts and file inventory are documented under root `docs/` and `contracts/`.

<!-- M3 End -->
