"""M3/M4 - File Intake Module Start
Exposes accepted-file ingestion creation and status lookup endpoints.
M3/M4 End"""

import hmac
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Response, UploadFile

from app.config import settings
from app.models.ingestion import IngestionOptions, IngestionRecord, SourceContext, SourceType
from app.models.validation import ValidationStatus
from app.services.ingestion_service import create_ingestion_record, get_ingestion_record, load_ingestion_content


router = APIRouter(prefix="/ingestions", tags=["file-ingestion"])


@router.post("", response_model=IngestionRecord)
async def create_ingestion(
    file: UploadFile = File(...),
    validation_status: ValidationStatus = Form(...),
    validation_sha256: Optional[str] = Form(default=None),
    detected_mime_type: Optional[str] = Form(default=None),
    source_type: SourceType = Form(default=SourceType.api),
    source_id: Optional[str] = Form(default=None),
    submitted_by: Optional[str] = Form(default=None),
    workflow: Optional[str] = Form(default=None),
    idempotency_key: Optional[str] = Form(default=None),
    priority: str = Form(default="normal"),
) -> IngestionRecord:
    content = await file.read()

    return create_ingestion_record(
        content=content,
        filename=file.filename or "",
        provided_content_type=file.content_type,
        validation_status=validation_status,
        validation_sha256=validation_sha256,
        detected_mime_type=detected_mime_type,
        source=SourceContext(
            source_type=source_type,
            source_id=source_id,
            submitted_by=submitted_by,
        ),
        options=IngestionOptions(
            workflow=workflow or settings.default_workflow,
            idempotency_key=idempotency_key,
            priority=priority,
        ),
        storage_root=settings.storage_root,
        max_stored_file_size_bytes=settings.max_stored_file_size_bytes,
        storage_provider=settings.stats_storage_provider,
        azure_storage_account_name=settings.azure_storage_account_name,
        azure_storage_container_name=settings.azure_storage_container_name,
        azure_storage_connection_string=settings.azure_storage_connection_string,
        azure_storage_blob_prefix=settings.azure_storage_blob_prefix,
    )


@router.get("/{ingestion_id}", response_model=IngestionRecord)
def get_ingestion(ingestion_id: str) -> IngestionRecord:
    record = get_ingestion_record(ingestion_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Ingestion record was not found.")

    return record


def _require_internal_key(internal_api_key: Optional[str]) -> None:
    # The stored original bytes are sensitive (raw financial documents), so this
    # read-back is server-to-server only. M12 sends X-Stats-Internal-Key. If no key
    # is configured the endpoint stays locked rather than open.
    expected = settings.stats_internal_api_key
    if not expected or not internal_api_key or not hmac.compare_digest(internal_api_key, expected):
        raise HTTPException(status_code=401, detail="Internal service key is required.")


@router.get("/{ingestion_id}/content")
def get_ingestion_content(
    ingestion_id: str,
    internal_api_key: Optional[str] = Header(default=None, alias="X-Stats-Internal-Key"),
) -> Response:
    """Stream the stored original bytes for a previously accepted ingestion.

    Internal-key only (additive read-back used by automated re-ingestion). The
    create/get behaviour and the manual Upload flow are unchanged.
    """
    _require_internal_key(internal_api_key)
    try:
        loaded = load_ingestion_content(
            ingestion_id=ingestion_id,
            storage_root=settings.storage_root,
            storage_provider=settings.stats_storage_provider,
            azure_storage_account_name=settings.azure_storage_account_name,
            azure_storage_container_name=settings.azure_storage_container_name,
            azure_storage_connection_string=settings.azure_storage_connection_string,
            azure_storage_blob_prefix=settings.azure_storage_blob_prefix,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if loaded is None:
        raise HTTPException(status_code=404, detail="Stored content was not found for this ingestion.")

    content, media_type, filename = loaded
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
