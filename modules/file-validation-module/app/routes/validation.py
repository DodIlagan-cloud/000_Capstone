"""M3 - File Validation Module Start
Exposes the file validation request/result API for uploaded file candidates.
M3 End"""

from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from app.config import settings
from app.models.validation import FileValidationPolicy, FileValidationResult
from app.services.validation_service import validate_file_content


router = APIRouter(prefix="/files", tags=["file-validation"])


def _csv_or_default(value: Optional[str], default: list[str], normalize_extension: bool = False) -> list[str]:
    if value is None:
        return default

    parsed_values = []
    for raw_value in value.split(","):
        normalized_value = raw_value.strip().lower()
        if normalize_extension and normalized_value and not normalized_value.startswith("."):
            normalized_value = f".{normalized_value}"
        if normalized_value:
            parsed_values.append(normalized_value)

    return parsed_values


@router.post("/validate", response_model=FileValidationResult)
async def validate_file(
    file: UploadFile = File(...),
    allowed_extensions: Optional[str] = Form(default=None),
    allowed_mime_types: Optional[str] = Form(default=None),
    max_size_bytes: Optional[int] = Form(default=None),
    require_known_signature: Optional[bool] = Form(default=None),
    compute_sha256: Optional[bool] = Form(default=None),
) -> FileValidationResult:
    policy = FileValidationPolicy(
        allowed_extensions=_csv_or_default(
            allowed_extensions,
            settings.allowed_extensions,
            normalize_extension=True,
        ),
        allowed_mime_types=_csv_or_default(allowed_mime_types, settings.allowed_mime_types),
        max_size_bytes=max_size_bytes if max_size_bytes is not None else settings.max_file_size_bytes,
        require_known_signature=(
            require_known_signature
            if require_known_signature is not None
            else settings.require_known_signature
        ),
        compute_sha256=compute_sha256 if compute_sha256 is not None else settings.compute_sha256,
    )
    content = await file.read()

    return validate_file_content(
        content=content,
        filename=file.filename or "",
        provided_content_type=file.content_type,
        policy=policy,
    )
