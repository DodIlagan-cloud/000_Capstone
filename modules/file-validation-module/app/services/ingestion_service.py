"""M3/M4 - File Intake Module Start
Implements ingestion record creation and status tracking for accepted files.
M3/M4 End"""

import hashlib
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.models.ingestion import (
    DocumentHandoff,
    FindingSeverity,
    IngestionFinding,
    IngestionOptions,
    IngestionRecord,
    IngestionStatus,
    SourceContext,
    ValidationSummary,
)
from app.models.validation import ValidationStatus
from app.services.storage_service import StorageSettings, load_intake_content, store_intake_content


_records: dict[str, IngestionRecord] = {}
_idempotency_index: dict[str, str] = {}


def reset_ingestion_store() -> None:
    """Clear in-memory ingestion state for tests and local restarts."""
    _records.clear()
    _idempotency_index.clear()


def get_ingestion_record(ingestion_id: str) -> Optional[IngestionRecord]:
    return _records.get(ingestion_id)


def load_ingestion_content(
    *,
    ingestion_id: str,
    storage_root: Path,
    storage_provider: str = "LocalFileSystem",
    azure_storage_account_name: str = "",
    azure_storage_container_name: str = "",
    azure_storage_connection_string: str = "",
    azure_storage_blob_prefix: str = "intake",
) -> Optional[tuple[bytes, str, str]]:
    """Read back stored intake content for a previously accepted file.

    Returns (content, media_type, filename) or None when the record/handoff is
    missing. Additive: does not change ingestion creation or status behaviour.
    """
    record = _records.get(ingestion_id)
    if record is None or record.handoff is None:
        return None
    content = load_intake_content(
        ingestion_id=ingestion_id,
        normalized_filename=record.handoff.normalized_filename,
        settings=StorageSettings(
            provider=storage_provider,
            storage_root=storage_root,
            azure_account_name=azure_storage_account_name,
            azure_container_name=azure_storage_container_name,
            azure_connection_string=azure_storage_connection_string,
            azure_blob_prefix=azure_storage_blob_prefix,
        ),
    )
    media_type = record.handoff.detected_mime_type or "application/octet-stream"
    return content, media_type, record.handoff.normalized_filename


def create_ingestion_record(
    *,
    content: bytes,
    filename: str,
    provided_content_type: Optional[str],
    validation_status: ValidationStatus,
    validation_sha256: Optional[str],
    detected_mime_type: Optional[str],
    source: SourceContext,
    options: IngestionOptions,
    storage_root: Path,
    max_stored_file_size_bytes: int,
    storage_provider: str = "LocalFileSystem",
    azure_storage_account_name: str = "",
    azure_storage_container_name: str = "",
    azure_storage_connection_string: str = "",
    azure_storage_blob_prefix: str = "intake",
) -> IngestionRecord:
    now = datetime.now(timezone.utc)
    content_sha256 = hashlib.sha256(content).hexdigest()
    idempotency_key = options.idempotency_key or validation_sha256 or content_sha256

    if idempotency_key in _idempotency_index:
        existing_record = _records[_idempotency_index[idempotency_key]]
        duplicate_record = existing_record.model_copy(deep=True)
        duplicate_record.status = IngestionStatus.duplicate
        duplicate_record.updated_at_utc = now
        duplicate_record.findings.append(
            IngestionFinding(
                code="DUPLICATE_SUBMISSION",
                severity=FindingSeverity.warning,
                message="An ingestion record already exists for this idempotency key or file hash.",
            )
        )
        return duplicate_record

    ingestion_id = str(uuid.uuid4())
    validation = ValidationSummary(
        status=validation_status.value,
        sha256=validation_sha256 or content_sha256,
        detected_mime_type=detected_mime_type or provided_content_type,
    )

    findings: list[IngestionFinding] = []
    if validation_status != ValidationStatus.accepted:
        findings.append(
            IngestionFinding(
                code="VALIDATION_NOT_ACCEPTED",
                severity=FindingSeverity.error,
                message="Only validation-accepted files can be ingested.",
            )
        )

    if not content:
        findings.append(
            IngestionFinding(
                code="EMPTY_FILE",
                severity=FindingSeverity.error,
                message="Ingestion content cannot be empty.",
            )
        )

    if len(content) > max_stored_file_size_bytes:
        findings.append(
            IngestionFinding(
                code="FILE_TOO_LARGE",
                severity=FindingSeverity.error,
                message="File exceeds the configured ingestion storage limit.",
            )
        )

    if findings:
        record = IngestionRecord(
            ingestion_id=ingestion_id,
            status=IngestionStatus.rejected,
            created_at_utc=now,
            updated_at_utc=now,
            source=source,
            options=options,
            validation=validation,
            findings=findings,
        )
        _records[ingestion_id] = record
        return record

    normalized_filename = _normalize_filename(filename)
    try:
        stored_content = store_intake_content(
            content=content,
            ingestion_id=ingestion_id,
            normalized_filename=normalized_filename,
            content_type=detected_mime_type or provided_content_type,
            settings=StorageSettings(
                provider=storage_provider,
                storage_root=storage_root,
                azure_account_name=azure_storage_account_name,
                azure_container_name=azure_storage_container_name,
                azure_connection_string=azure_storage_connection_string,
                azure_blob_prefix=azure_storage_blob_prefix,
            ),
        )
    except RuntimeError as exc:
        record = IngestionRecord(
            ingestion_id=ingestion_id,
            status=IngestionStatus.rejected,
            created_at_utc=now,
            updated_at_utc=now,
            source=source,
            options=options,
            validation=validation,
            findings=[
                IngestionFinding(
                    code="INGESTION_STORAGE_FAILED",
                    severity=FindingSeverity.error,
                    message=str(exc),
                )
            ],
        )
        _records[ingestion_id] = record
        return record

    handoff = DocumentHandoff(
        ingestion_id=ingestion_id,
        original_filename=filename,
        normalized_filename=normalized_filename,
        content_reference=stored_content.content_reference,
        size_bytes=len(content),
        detected_mime_type=detected_mime_type or provided_content_type,
        sha256=validation.sha256,
        workflow=options.workflow,
    )
    record = IngestionRecord(
        ingestion_id=ingestion_id,
        status=IngestionStatus.queued,
        created_at_utc=now,
        updated_at_utc=now,
        source=source,
        options=options,
        validation=validation,
        handoff=handoff,
        findings=[],
    )
    _records[ingestion_id] = record
    _idempotency_index[idempotency_key] = ingestion_id
    return record


def _normalize_filename(filename: str) -> str:
    candidate = Path(filename or "document").name.strip().lower()
    normalized = re.sub(r"[^a-z0-9._-]+", "-", candidate).strip(".-")
    return normalized or "document"
