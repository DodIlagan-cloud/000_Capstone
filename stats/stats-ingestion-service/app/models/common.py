"""M0 Foundation: shared Pydantic response models."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Response model for API errors."""

    type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")


class HealthResponse(BaseModel):
    """Response model for service health."""

    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")


class RootResponse(BaseModel):
    """Response model for root service metadata."""

    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    message: str = Field(..., description="Service status message")
