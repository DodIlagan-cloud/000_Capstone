"""Shared API error definitions."""

from enum import Enum

from fastapi import HTTPException, status

from app.models.common import ErrorResponse


class ErrorType(str, Enum):
    """Reusable error type identifiers for API responses."""

    INVALID_REQUEST = "INVALID_REQUEST"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"


def api_error(
    error_type: ErrorType,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> HTTPException:
    """Build a consistent HTTPException payload."""
    return HTTPException(
        status_code=status_code,
        detail=ErrorResponse(type=error_type.value, message=message).model_dump(),
    )
