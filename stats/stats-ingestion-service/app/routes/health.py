"""Foundation health and service metadata routes."""

from fastapi import APIRouter

from app.config import settings
from app.models.common import HealthResponse, RootResponse

router = APIRouter(tags=["Foundation"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health metadata."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
    )


@router.get("/", response_model=RootResponse)
async def root() -> RootResponse:
    """Return basic service metadata."""
    return RootResponse(
        service=settings.app_name,
        version=settings.app_version,
        message="Stats Ingestion Service is running",
    )
