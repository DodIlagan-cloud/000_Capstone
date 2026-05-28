"""M5 - Document Parsing Module Start
Provides the document parsing upload endpoint.
M5/M6 End"""

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.models.parsing import DocumentParseResult
from app.services.parsing_service import parse_document_content


router = APIRouter(prefix="/parses", tags=["document-parsing"])


@router.post("", response_model=DocumentParseResult)
async def parse_document(
    file: UploadFile = File(...),
    ingestion_id: Optional[str] = Form(default=None),
    source_type: Optional[str] = Form(default=None),
    source_id: Optional[str] = Form(default=None),
    sha256: Optional[str] = Form(default=None),
    allow_direct_text: Optional[bool] = Form(default=None),
    allow_ocr_fallback: Optional[bool] = Form(default=None),
    language: Optional[str] = Form(default=None),
    page_limit: Optional[int] = Form(default=None),
    classification_threshold: Optional[float] = Form(default=None),
) -> DocumentParseResult:
    content = await file.read()

    return parse_document_content(
        content=content,
        filename=file.filename or "",
        provided_content_type=file.content_type,
        ingestion_id=ingestion_id,
        source_type=source_type,
        source_id=source_id,
        sha256=sha256,
        allow_direct_text=allow_direct_text,
        allow_ocr_fallback=allow_ocr_fallback,
        language=language,
        page_limit=page_limit,
        classification_threshold=classification_threshold,
    )
