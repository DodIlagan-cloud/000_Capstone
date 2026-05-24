<!-- M3 - File Validation Module Start -->
<!-- Specifies the standalone reusable File Validation Module. -->

# Module 3 File Validation Module Specification

## Module Summary

Module 3 establishes a standalone reusable File Validation Module for candidate documents entering the Stats processing workflow. It validates file size, extension, content signature, content type consistency, allowed policy rules, and optional SHA-256 hash generation.

This module does not store files, create ingestion jobs, perform OCR, classify documents, extract transactions, or update Stats-specific persistence. Those concerns belong to later modules.

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
| Module | File Validation Module |
| Type | Standalone module |
| Main responsibility | Validate file type, size, extension, signatures, hashes, rejection reasons |
| Reusable contract | File validation request/result API |
| Owner folder | `modules/file-validation-module/` |

## Goals

- Provide a standalone API for validating uploaded file candidates.
- Support automatic validation when a caller selects or receives a file.
- Keep validation rules configurable without source-code edits.
- Detect supported content signatures for PDF, PNG, and JPEG files.
- Reject empty, oversized, unsupported, and mismatched files with explicit finding codes.
- Return normalized file metadata and optional SHA-256 hashes.
- Keep the module reusable outside the Stats Web UI.
- Provide module-local automated tests.

## Non-Goals

- File persistence or storage.
- Ingestion record creation.
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

## API Contract

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | `GET` | Returns service health metadata. |
| `/` | `GET` | Returns root service metadata. |
| `/api/v1/files/validate` | `POST` | Validates a multipart uploaded file candidate against default or request policy. |

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
- Stats Web automatic validation on file selection, with rejected files showing findings and accepted files becoming eligible for the next parsing/ingestion step.

## Acceptance Criteria

M3 is complete when:

- `modules/file-validation-module/` contains the standalone runtime, configuration, README, and tests.
- The module exposes health/root endpoints and the versioned validation endpoint.
- Validation results include explicit status, metadata, findings, and applied policy.
- The expected UI behavior is automatic validation on file selection: rejected files show findings, accepted files are prepared for the next parsing/ingestion step.
- Runtime limits and allowed policy values are configurable.
- Module-local tests pass with `pytest`.
- Contracts and file inventory are documented under root `docs/` and `contracts/`.

<!-- M3 End -->
