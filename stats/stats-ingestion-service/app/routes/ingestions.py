"""M3/M4 - File Intake Module Start
Exposes ingestion creation and status lookup APIs from the merged intake service.
M3/M4 End"""

from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.models.ingestion import IngestionOptions, IngestionRecord, SourceContext, SourceType
from app.models.validation import ValidationStatus
from app.services.ingestion_service import create_ingestion_record, get_ingestion_record


router = APIRouter(prefix="/ingestions", tags=["file-ingestion"])


@router.post("", response_model=IngestionRecord)
async def create_ingestion(
    file: UploadFile = File(...),
    validation_status: ValidationStatus = Form(...),
    validation_sha256: Optional[str] = Form(default=None),
    detected_mime_type: Optional[str] = Form(default=None),
    source_type: SourceType = Form(default=SourceType.manual_upload),
    source_id: Optional[str] = Form(default=None),
    submitted_by: Optional[str] = Form(default=None),
    workflow: Optional[str] = Form(default=None),
    idempotency_key: Optional[str] = Form(default=None),
    priority: str = Form(default="normal"),
) -> IngestionRecord:
    content = await file.read()
    source = SourceContext(
        source_type=source_type,
        source_id=source_id,
        submitted_by=submitted_by,
    )
    options = IngestionOptions(
        workflow=workflow or settings.default_workflow,
        idempotency_key=idempotency_key,
        priority=priority,
    )

    return create_ingestion_record(
        content=content,
        filename=file.filename or "",
        provided_content_type=file.content_type,
        validation_status=validation_status,
        validation_sha256=validation_sha256,
        detected_mime_type=detected_mime_type,
        source=source,
        options=options,
        storage_root=settings.storage_root,
        max_stored_file_size_bytes=settings.max_stored_file_size_bytes,
    )


@router.get("/{ingestion_id}", response_model=IngestionRecord)
def get_ingestion(ingestion_id: str) -> IngestionRecord:
    record = get_ingestion_record(ingestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingestion record not found")

    return record
