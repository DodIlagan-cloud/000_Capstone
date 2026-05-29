"""M7 - Transaction Extraction Module Start
Provides health and root metadata endpoints for the Transaction Extraction API.
M7 End"""

from fastapi import APIRouter

from app.config import settings
from app.models.common import HealthResponse, RootResponse


router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        extraction={
            "supported_document_types": settings.supported_document_types,
            "default_currency": settings.default_currency,
            "min_transaction_confidence": settings.min_transaction_confidence,
            "field_extraction_enabled": settings.enable_field_extraction,
            "transaction_rows_enabled": settings.enable_transaction_rows,
        },
    )


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="Transaction Extraction Module is running",
    )
