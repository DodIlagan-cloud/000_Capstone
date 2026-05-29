"""M5 - Document Parsing Module Start
Defines document parsing contracts for extraction, classification, quality, and evidence.
M5/M6 End"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ParseStatus(str, Enum):
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    unsupported = "unsupported"


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ParseFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str


class DocumentTrace(BaseModel):
    original_filename: str
    normalized_filename: str
    size_bytes: int
    provided_content_type: Optional[str] = None
    detected_mime_type: Optional[str] = None
    ingestion_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    sha256: str


class PageParseResult(BaseModel):
    page_number: int
    text: str
    text_length: int
    empty: bool


class ParseMetadata(BaseModel):
    extraction_method: str
    ocr_engine: Optional[str] = None
    page_count: int
    pages_processed: int
    elapsed_ms: int
    language: str
    page_limit: int
    ocr_quality_score: Optional[float] = None
    ocr_mean_confidence: Optional[float] = None
    ocr_selected_orientation: Optional[int] = None
    ocr_selected_psm: Optional[int] = None
    ocr_attempt_count: int = 0


class StrategyDecision(BaseModel):
    selected_strategy: str
    reason: str
    direct_text_attempted: bool
    ocr_attempted: bool
    tesseract_available: bool


class ClassificationResult(BaseModel):
    document_type: str
    confidence: float
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)


class QualityMetadata(BaseModel):
    text_length: int
    page_count: int
    pages_processed: int
    empty_page_count: int
    low_text: bool


class EvaluationMetadata(BaseModel):
    document_id: str
    input_media_type: Optional[str]
    strategy: str
    status: ParseStatus
    page_count: int
    pages_processed: int
    text_length: int
    empty_page_count: int
    elapsed_ms: int
    finding_counts: dict[str, int]
    redaction_applied: bool
    redaction_finding_counts: dict[str, int]
    predicted_document_type: str
    classification_confidence: float
    classification_reason_codes: list[str]
    classification_status: str


class RedactedEvidencePreview(BaseModel):
    redacted_text_preview: str
    redaction_counts: dict[str, int]
    redaction_applied: bool


class M7HandoffAudit(BaseModel):
    parse_id: str
    document_id: str
    filename: str
    strategy: str
    extraction_method: str
    ocr_engine: Optional[str] = None
    ocr_attempted: bool
    tesseract_available: bool
    status: ParseStatus
    confidence: float
    text_length: int
    page_count: int
    pages_processed: int
    warnings: list[str] = Field(default_factory=list)
    m7_ready: bool
    m7_readiness_reason_codes: list[str] = Field(default_factory=list)
    transaction_signal_count: int
    redacted_preview: str
    redaction_summary: dict[str, int]
    redaction_applied: bool


class DocumentParseResult(BaseModel):
    parse_id: str
    status: ParseStatus
    document: DocumentTrace
    text: str
    pages: list[PageParseResult]
    metadata: ParseMetadata
    strategy: StrategyDecision
    classification: ClassificationResult
    quality: QualityMetadata
    evaluation: EvaluationMetadata
    evidence: RedactedEvidencePreview
    m7_handoff: M7HandoffAudit
    findings: list[ParseFinding] = Field(default_factory=list)
