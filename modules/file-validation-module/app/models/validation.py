"""M3 - File Validation Module Start
Defines file validation contracts shared by the API and validation service.
M3 End"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    accepted = "accepted"
    rejected = "rejected"


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"


class FileValidationPolicy(BaseModel):
    allowed_extensions: List[str] = Field(default_factory=list)
    allowed_mime_types: List[str] = Field(default_factory=list)
    max_size_bytes: int
    require_known_signature: bool = True
    compute_sha256: bool = True


class FileMetadata(BaseModel):
    original_filename: str
    normalized_filename: str
    size_bytes: int
    extension: str
    provided_content_type: Optional[str] = None
    detected_mime_type: Optional[str] = None
    sha256: Optional[str] = None


class ValidationFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str


class FileValidationResult(BaseModel):
    status: ValidationStatus
    metadata: FileMetadata
    findings: List[ValidationFinding] = Field(default_factory=list)
    policy: FileValidationPolicy
