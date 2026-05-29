"""M7 - Transaction Extraction Module Start
Defines transaction extraction request and result contracts.
M7 End"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ExtractionStatus(str, Enum):
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    unsupported = "unsupported"


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ExtractionFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str


class SourceDocument(BaseModel):
    original_filename: Optional[str] = None
    normalized_filename: Optional[str] = None
    ingestion_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    sha256: Optional[str] = None


class ParsedPageText(BaseModel):
    page_number: int
    text: str


class ParsedClassification(BaseModel):
    document_type: str = "unknown"
    confidence: Optional[float] = None
    status: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)


class ParsedQuality(BaseModel):
    text_length: Optional[int] = None
    page_count: Optional[int] = None
    pages_processed: Optional[int] = None
    empty_page_count: Optional[int] = None
    low_text: Optional[bool] = None


class UpstreamFinding(BaseModel):
    code: str
    severity: Optional[str] = None
    message: Optional[str] = None


class ExtractionOptions(BaseModel):
    min_confidence: Optional[float] = None
    page_limit: Optional[int] = None
    enable_field_extraction: Optional[bool] = None
    enable_transaction_rows: Optional[bool] = None


class TransactionExtractionRequest(BaseModel):
    parse_id: Optional[str] = None
    document: Optional[SourceDocument] = None
    document_type: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification: Optional[ParsedClassification] = None
    text: str = ""
    pages: list[ParsedPageText] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    quality: Optional[ParsedQuality] = None
    findings: list[UpstreamFinding] = Field(default_factory=list)
    options: Optional[ExtractionOptions] = None


class SourceReference(BaseModel):
    page_number: Optional[int] = None
    line_number: int
    text: str


class TransactionCandidate(BaseModel):
    candidate_id: str
    date_text: Optional[str] = None
    description: str
    amount: float
    currency: str
    direction: str
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class FinancialFieldCandidate(BaseModel):
    field_name: str
    value_text: str
    normalized_value: Optional[str] = None
    currency: Optional[str] = None
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    transaction_candidate_count: int
    financial_field_candidate_count: int
    debit_total: float
    credit_total: float
    amount_total: float
    pages_processed: int
    text_length: int
    low_confidence_candidate_count: int


class ExtractionEvaluation(BaseModel):
    extraction_id: str
    parse_id: Optional[str] = None
    document_type: str
    status: ExtractionStatus
    transaction_candidate_count: int
    financial_field_candidate_count: int
    finding_counts: dict[str, int]
    min_confidence: float
    text_length: int
    pages_processed: int


class TransactionExtractionResult(BaseModel):
    extraction_id: str
    status: ExtractionStatus
    parse_id: Optional[str] = None
    document: Optional[SourceDocument] = None
    document_type: str
    transaction_candidates: list[TransactionCandidate] = Field(default_factory=list)
    financial_field_candidates: list[FinancialFieldCandidate] = Field(default_factory=list)
    summary: ExtractionSummary
    evaluation: ExtractionEvaluation
    findings: list[ExtractionFinding] = Field(default_factory=list)
