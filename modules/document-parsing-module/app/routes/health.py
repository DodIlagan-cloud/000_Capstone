"""M5 - Document Parsing Module Start
Provides health and root metadata endpoints for the Document Parsing API.
M5/M6 End"""

from fastapi import APIRouter

from app.config import settings
from app.models.common import HealthResponse, OcrReadiness, RootResponse
from app.services.parsing_service import get_ocr_readiness


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        ocr=OcrReadiness(**get_ocr_readiness()),
    )


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="Document Parsing Module is running",
    )
