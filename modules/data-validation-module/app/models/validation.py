"""M8 - Data Validation Module Start
Defines data validation request and result contracts.
M8 End"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ValidationStatus(str, Enum):
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"


class FindingSeverity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ValidationFinding(BaseModel):
    code: str
    severity: FindingSeverity
    message: str
    record_id: Optional[str] = None


class SourceDocument(BaseModel):
    original_filename: Optional[str] = None
    normalized_filename: Optional[str] = None
    ingestion_id: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    sha256: Optional[str] = None


class SourceReference(BaseModel):
    page_number: Optional[int] = None
    line_number: int
    text: str


class TransactionCandidateInput(BaseModel):
    candidate_id: str
    date_text: Optional[str] = None
    description: str = ""
    amount: float
    currency: Optional[str] = None
    direction: str = "unknown"
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class FinancialFieldCandidateInput(BaseModel):
    field_name: str
    value_text: str
    normalized_value: Optional[str] = None
    currency: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class ValidationOptions(BaseModel):
    min_confidence: Optional[float] = None
    enable_duplicate_detection: Optional[bool] = None
    require_transaction_date: Optional[bool] = None
    require_transaction_direction: Optional[bool] = None


class DataValidationRequest(BaseModel):
    extraction_id: Optional[str] = None
    parse_id: Optional[str] = None
    document: Optional[SourceDocument] = None
    document_type: str = "unknown"
    transaction_candidates: list[TransactionCandidateInput] = Field(default_factory=list)
    financial_field_candidates: list[FinancialFieldCandidateInput] = Field(default_factory=list)
    findings: list[ValidationFinding] = Field(default_factory=list)
    options: Optional[ValidationOptions] = None


class NormalizedTransactionRecord(BaseModel):
    record_id: str
    source_candidate_id: str
    transaction_date: Optional[str] = None
    description: str
    amount: float
    currency: str
    direction: str
    signed_amount: float
    source: Optional[SourceReference] = None
    confidence: float
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)
    duplicate_of: Optional[str] = None


class NormalizedFinancialField(BaseModel):
    field_name: str
    value: str
    currency: Optional[str] = None
    confidence: float
    source: Optional[SourceReference] = None
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    input_transaction_candidate_count: int
    normalized_record_count: int
    valid_record_count: int
    warning_record_count: int
    invalid_record_count: int
    duplicate_record_count: int
    financial_field_count: int
    debit_total: float
    credit_total: float
    net_total: float


class ValidationEvaluation(BaseModel):
    validation_id: str
    extraction_id: Optional[str] = None
    parse_id: Optional[str] = None
    document_type: str
    status: ValidationStatus
    finding_counts: dict[str, int]
    min_confidence: float
    duplicate_detection_enabled: bool
    normalized_record_count: int
    valid_record_count: int


class DataValidationResult(BaseModel):
    validation_id: str
    status: ValidationStatus
    extraction_id: Optional[str] = None
    parse_id: Optional[str] = None
    document: Optional[SourceDocument] = None
    document_type: str
    normalized_records: list[NormalizedTransactionRecord] = Field(default_factory=list)
    financial_fields: list[NormalizedFinancialField] = Field(default_factory=list)
    summary: ValidationSummary
    evaluation: ValidationEvaluation
    findings: list[ValidationFinding] = Field(default_factory=list)
