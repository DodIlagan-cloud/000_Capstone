"""M8 - Data Validation Module Start
Provides health and root endpoints.
M8 End"""

from fastapi import APIRouter

from app.config import settings
from app.models.common import HealthResponse, RootResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        validation={
            "default_currency": settings.default_currency,
            "min_record_confidence": settings.min_record_confidence,
            "duplicate_detection_enabled": settings.enable_duplicate_detection,
            "max_records_per_request": settings.max_records_per_request,
        },
    )


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="Data Validation Module is running",
    )
