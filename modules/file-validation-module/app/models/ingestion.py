"""M3/M4 - File Intake Module Start
Defines ingestion contracts for the merged validation and ingestion API.
M3/M4 End"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IngestionStatus(str, Enum):
    queued = "queued"
    rejected = "rejected"
    duplicate = "duplicate"
    failed = "failed"


class SourceType(str, Enum):
    manual_upload = "manual_upload"
    email_attachment = "email_attachment"
    batch_import = "batch_import"
    api = "api"


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class IngestionFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str


class SourceContext(BaseModel):
    source_type: SourceType
    source_id: Optional[str] = None
    submitted_by: Optional[str] = None


class IngestionOptions(BaseModel):
    workflow: str
    idempotency_key: Optional[str] = None
    priority: str = "normal"


class ValidationSummary(BaseModel):
    status: str
    sha256: Optional[str] = None
    detected_mime_type: Optional[str] = None


class DocumentHandoff(BaseModel):
    ingestion_id: str
    original_filename: str
    normalized_filename: str
    content_reference: Optional[str] = None
    size_bytes: int
    detected_mime_type: Optional[str] = None
    sha256: Optional[str] = None
    workflow: str


class IngestionRecord(BaseModel):
    ingestion_id: str
    status: IngestionStatus
    created_at_utc: datetime
    updated_at_utc: datetime
    source: SourceContext
    options: IngestionOptions
    validation: ValidationSummary
    handoff: Optional[DocumentHandoff] = None
    findings: List[IngestionFinding] = Field(default_factory=list)
