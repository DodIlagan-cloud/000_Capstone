"""M12 - Email Ingestion Module Start
Provides health and root metadata endpoints for the Email Ingestion API.
M12 End"""

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
        provider=settings.email_provider,
        mode=settings.email_ingestion_mode,
    )


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="Email Ingestion Module is running",
    )
