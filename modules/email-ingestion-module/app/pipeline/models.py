"""M12 - Email Ingestion Module Start
Automated pipeline data models.

Stdlib dataclasses (no pydantic) so the orchestration core can run and be tested
with no third-party dependencies. The trigger boundary can wrap these with request
validation.
M12 End"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineRunRequest:
    """One automated document to push through parse -> ... -> save."""

    ingestion_id: str
    original_filename: str
    source_type: str = "email_attachment"
    source_id: Optional[str] = None
    sha256: Optional[str] = None
    # Phase A sources content from the trigger (M12 already holds the bytes at
    # handoff). Phase C adds Blob fetch by storage_reference for the Event Grid path.
    content_base64: Optional[str] = None
    storage_reference: Optional[str] = None
    content_type: Optional[str] = None
    uploaded_by_user_id: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class PipelineStep:
    name: str
    status: str
    detail: Optional[str] = None


@dataclass
class PipelineRunResult:
    ingestion_id: str
    status: str = "failed"  # completed | failed
    job_id: Optional[str] = None
    document_id: Optional[str] = None
    parse_id: Optional[str] = None
    extraction_id: Optional[str] = None
    validation_id: Optional[str] = None
    saved_record_count: int = 0
    review_item_count: int = 0
    warning_record_count: int = 0
    invalid_record_count: int = 0
    steps: list = field(default_factory=list)
    error: Optional[str] = None
