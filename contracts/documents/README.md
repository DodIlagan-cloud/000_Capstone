# Document Contracts

<!-- M0 Foundation: target folder for document intake contracts. -->

This folder will hold document and file-processing handoff contracts such as:

- file candidate
- file validation result
- ingestion handoff
- document metadata

These contracts should let File Validation, File Ingestion, OCR Extraction, and Stats workflow integration communicate without importing each other's internals.

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
