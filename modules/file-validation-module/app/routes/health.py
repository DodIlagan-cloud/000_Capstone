"""M3 - File Validation Module Start
Provides health and root metadata endpoints for the File Validation API.
M3 End"""

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
    )


@router.get("/", response_model=RootResponse)
def root() -> RootResponse:
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="File Validation Module is running",
    )
