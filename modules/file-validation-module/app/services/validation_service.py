"""M3 - File Validation Module Start
Implements reusable policy-driven file validation without Stats-specific ingestion logic.
M3 End"""

import hashlib
from pathlib import Path
from typing import Optional

from app.models.validation import (
    FileMetadata,
    FileValidationPolicy,
    FileValidationResult,
    FindingSeverity,
    ValidationFinding,
    ValidationStatus,
)


SIGNATURES = (
    ("application/pdf", b"%PDF"),
    ("image/png", b"\x89PNG\r\n\x1a\n"),
    ("image/jpeg", b"\xff\xd8\xff"),
)

EXPECTED_EXTENSIONS_BY_MIME = {
    "application/pdf": {".pdf"},
    "image/png": {".png"},
    "image/jpeg": {".jpg", ".jpeg"},
}


def normalize_extension(filename: str) -> str:
    """Return a lowercase file extension including the leading dot."""
    return Path(filename or "").suffix.lower()


def normalize_filename(filename: str) -> str:
    """Return only the final filename segment so callers do not leak client paths."""
    return Path(filename or "unnamed").name or "unnamed"


def detect_mime_type(content: bytes) -> Optional[str]:
    """Detect supported MIME types from leading file signatures."""
    for mime_type, signature in SIGNATURES:
        if content.startswith(signature):
            return mime_type

    return None


def _finding(code: str, message: str, severity: FindingSeverity = FindingSeverity.error) -> ValidationFinding:
    return ValidationFinding(code=code, severity=severity, message=message)


def validate_file_content(
    content: bytes,
    filename: str,
    provided_content_type: Optional[str],
    policy: FileValidationPolicy,
) -> FileValidationResult:
    """Validate a candidate file and return explicit metadata and findings."""
    normalized_filename = normalize_filename(filename)
    extension = normalize_extension(normalized_filename)
    detected_mime_type = detect_mime_type(content)
    size_bytes = len(content)
    findings: list[ValidationFinding] = []

    if size_bytes == 0:
        findings.append(_finding("EMPTY_FILE", "File content is empty."))

    if policy.max_size_bytes > 0 and size_bytes > policy.max_size_bytes:
        findings.append(_finding("FILE_TOO_LARGE", "File exceeds the configured maximum size."))

    if not extension:
        findings.append(_finding("MISSING_EXTENSION", "File has no extension."))
    elif policy.allowed_extensions and extension not in policy.allowed_extensions:
        findings.append(_finding("UNSUPPORTED_EXTENSION", "File extension is not allowed by policy."))

    if policy.require_known_signature and detected_mime_type is None and size_bytes > 0:
        findings.append(_finding("UNKNOWN_SIGNATURE", "File signature is not a supported document type."))

    if detected_mime_type and policy.allowed_mime_types and detected_mime_type not in policy.allowed_mime_types:
        findings.append(_finding("UNSUPPORTED_TYPE", "Detected file type is not allowed by policy."))

    if detected_mime_type and extension:
        expected_extensions = EXPECTED_EXTENSIONS_BY_MIME.get(detected_mime_type, set())
        if expected_extensions and extension not in expected_extensions:
            findings.append(
                _finding(
                    "SIGNATURE_EXTENSION_MISMATCH",
                    "File extension does not match detected content signature.",
                )
            )

    normalized_content_type = provided_content_type.lower() if provided_content_type else None
    if normalized_content_type and detected_mime_type and normalized_content_type != detected_mime_type:
        findings.append(
            _finding(
                "CONTENT_TYPE_MISMATCH",
                "Provided content type does not match detected file signature.",
                FindingSeverity.warning,
            )
        )

    metadata = FileMetadata(
        original_filename=filename or "",
        normalized_filename=normalized_filename,
        size_bytes=size_bytes,
        extension=extension,
        provided_content_type=normalized_content_type,
        detected_mime_type=detected_mime_type,
        sha256=hashlib.sha256(content).hexdigest() if policy.compute_sha256 else None,
    )
    has_error = any(finding.severity == FindingSeverity.error for finding in findings)

    return FileValidationResult(
        status=ValidationStatus.rejected if has_error else ValidationStatus.accepted,
        metadata=metadata,
        findings=findings,
        policy=policy,
    )
