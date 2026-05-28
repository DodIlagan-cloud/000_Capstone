"""M3 - File Validation Module Start
Tests reusable file validation policy checks and result metadata.
M3 End"""

from app.models.validation import FileValidationPolicy, ValidationStatus
from app.services.validation_service import validate_file_content


def default_policy(**overrides):
    values = {
        "allowed_extensions": [".pdf", ".png", ".jpg", ".jpeg"],
        "allowed_mime_types": ["application/pdf", "image/png", "image/jpeg"],
        "max_size_bytes": 1024,
        "require_known_signature": True,
        "compute_sha256": True,
    }
    values.update(overrides)
    return FileValidationPolicy(**values)


def finding_codes(result):
    return {finding.code for finding in result.findings}


def test_valid_pdf_is_accepted_with_metadata_and_hash():
    result = validate_file_content(
        content=b"%PDF-1.7\ncontent",
        filename="statement.pdf",
        provided_content_type="application/pdf",
        policy=default_policy(),
    )

    assert result.status == ValidationStatus.accepted
    assert result.metadata.extension == ".pdf"
    assert result.metadata.detected_mime_type == "application/pdf"
    assert len(result.metadata.sha256) == 64
    assert result.findings == []


def test_empty_file_is_rejected():
    result = validate_file_content(
        content=b"",
        filename="statement.pdf",
        provided_content_type="application/pdf",
        policy=default_policy(),
    )

    assert result.status == ValidationStatus.rejected
    assert "EMPTY_FILE" in finding_codes(result)


def test_oversized_file_is_rejected():
    result = validate_file_content(
        content=b"%PDF" + b"x" * 20,
        filename="statement.pdf",
        provided_content_type="application/pdf",
        policy=default_policy(max_size_bytes=8),
    )

    assert result.status == ValidationStatus.rejected
    assert "FILE_TOO_LARGE" in finding_codes(result)


def test_extension_content_mismatch_is_rejected():
    result = validate_file_content(
        content=b"%PDF-1.7\ncontent",
        filename="statement.png",
        provided_content_type="image/png",
        policy=default_policy(),
    )

    assert result.status == ValidationStatus.rejected
    assert "SIGNATURE_EXTENSION_MISMATCH" in finding_codes(result)
    assert "CONTENT_TYPE_MISMATCH" in finding_codes(result)


def test_unsupported_file_type_is_rejected():
    result = validate_file_content(
        content=b"not a known document",
        filename="notes.txt",
        provided_content_type="text/plain",
        policy=default_policy(),
    )

    codes = finding_codes(result)

    assert result.status == ValidationStatus.rejected
    assert "UNSUPPORTED_EXTENSION" in codes
    assert "UNKNOWN_SIGNATURE" in codes
