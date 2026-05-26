# Document Contracts

<!-- M0 Foundation: target folder for document intake contracts. -->

This folder will hold document and file-processing handoff contracts such as:

- file candidate
- file validation and ingestion result
- document handoff
- document metadata

These contracts should let File Validation and Ingestion, OCR Extraction, and Stats workflow integration communicate without importing each other's internals.

<!-- M3 - File Validation Module Start -->
<!-- Defines the concrete file validation request/result contract introduced by M3. -->

## M3 File Validation Contract

The File Validation Module accepts a multipart file candidate plus optional policy overrides.

### Request

| Field | Required | Description |
| --- | --- | --- |
| `file` | Yes | Candidate file content, filename, and browser-provided content type. |
| `allowed_extensions` | No | Comma-separated extension policy override such as `.pdf,.png`. |
| `allowed_mime_types` | No | Comma-separated detected MIME type policy override. |
| `max_size_bytes` | No | Maximum accepted file size for this request. |
| `require_known_signature` | No | Whether unknown signatures should reject the file. |
| `compute_sha256` | No | Whether the result should include a SHA-256 hash. |

### Result

| Field | Description |
| --- | --- |
| `status` | `accepted` or `rejected`. |
| `metadata` | Normalized filename, original filename, extension, size, provided content type, detected MIME type, and optional SHA-256 hash. |
| `findings` | Warning/error codes and messages explaining validation outcomes. |
| `policy` | The validation policy applied to the candidate file. |

The contract is intentionally limited to validation. It does not create ingestion records, store files, run OCR, or make Stats-specific workflow decisions.

<!-- M3 End -->

<!-- M3/M4 - File Intake Module Start -->
<!-- Defines the concrete ingestion request/status contract introduced by M4. -->

## M4 Ingestion Contract In The Merged Intake Module

The merged File Validation and Ingestion Module accepts a multipart file plus validation summary and source context. Only validation-accepted files are queued for downstream handoff.

### Request

| Field | Required | Description |
| --- | --- | --- |
| `file` | Yes | Accepted file content, filename, and browser-provided content type. |
| `validation_status` | Yes | Validation result status from the File Validation Module. |
| `validation_sha256` | No | Hash returned by validation, used for traceability and idempotency. |
| `detected_mime_type` | No | Detected type returned by validation. |
| `source_type` | No | Source lane such as `manual_upload`, `email_attachment`, `batch_import`, or `api`. |
| `source_id` | No | Source-specific identifier such as upload/session/email ID. |
| `submitted_by` | No | User or caller identifier. |
| `workflow` | No | Target workflow name. |
| `idempotency_key` | No | Duplicate-submission key supplied by the caller. |
| `priority` | No | Processing priority label. |

### Result

| Field | Description |
| --- | --- |
| `ingestion_id` | Stable identifier for the intake attempt. |
| `status` | `queued`, `rejected`, `duplicate`, or `failed`. |
| `source` | Normalized source context. |
| `options` | Workflow, idempotency key, and priority applied to the record. |
| `validation` | Validation status, hash, and detected media type summary. |
| `handoff` | Normalized document handoff with content reference when queued. |
| `findings` | Warning/error codes explaining rejected or duplicate outcomes. |

The contract is intentionally limited to intake tracking and downstream document handoff. It does not perform validation, OCR, classification, extraction, data-quality checks, or Stats-specific persistence.

<!-- M3/M4 End -->
