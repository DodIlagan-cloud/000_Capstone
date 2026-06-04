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
    section_id: Optional[str] = None
    section_label: Optional[str] = None
    source_text_redacted: Optional[str] = None
    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None


class TransactionCandidateInput(BaseModel):
    candidate_id: str
    date_text: Optional[str] = None
    posted_date_text: Optional[str] = None
    description: str = ""
    amount: float
    currency: Optional[str] = None
    direction: str = "unknown"
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class FinancialFieldCandidateInput(BaseModel):
    field_name: str
    field_label: Optional[str] = None
    value_type: str = "text"
    value_text: str
    normalized_value: Optional[str] = None
    currency: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class SectionCandidateInput(BaseModel):
    section_id: str
    section_label: str
    page_number: Optional[int] = None
    first_line_number: int
    last_line_number: int
    source_text_redacted: str
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class EntityCandidateInput(BaseModel):
    entity_id: str
    entity_type: str
    value_text: str
    normalized_value: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class ReferenceCandidateInput(BaseModel):
    reference_id: str
    reference_type: str
    value_text: str
    normalized_value: Optional[str] = None
    masked: bool = False
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class LineItemCandidateInput(BaseModel):
    line_item_id: str
    description: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class InstallmentCandidateInput(BaseModel):
    installment_id: str
    purchase_date_text: Optional[str] = None
    posted_date_text: Optional[str] = None
    description: str = ""
    principal_amount: Optional[float] = None
    current_billing_amount: Optional[float] = None
    remaining_balance: Optional[float] = None
    currency: Optional[str] = None
    term_text: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float = 0.0
    reason_codes: list[str] = Field(default_factory=list)


class ValidationOptions(BaseModel):
    min_confidence: Optional[float] = None
    enable_duplicate_detection: Optional[bool] = None
    require_transaction_date: Optional[bool] = None
    require_transaction_direction: Optional[bool] = None


class ReconciliationInput(BaseModel):
    status: str = "not_available"
    previous_balance: Optional[float] = None
    debit_total: Optional[float] = None
    credit_total: Optional[float] = None
    total_due: Optional[float] = None
    computed_total_due: Optional[float] = None
    difference: Optional[float] = None
    reason_codes: list[str] = Field(default_factory=list)


class DataValidationRequest(BaseModel):
    extraction_id: Optional[str] = None
    parse_id: Optional[str] = None
    document: Optional[SourceDocument] = None
    document_type: str = "unknown"
    transaction_candidates: list[TransactionCandidateInput] = Field(default_factory=list)
    financial_field_candidates: list[FinancialFieldCandidateInput] = Field(default_factory=list)
    section_candidates: list[SectionCandidateInput] = Field(default_factory=list)
    entity_candidates: list[EntityCandidateInput] = Field(default_factory=list)
    reference_candidates: list[ReferenceCandidateInput] = Field(default_factory=list)
    line_item_candidates: list[LineItemCandidateInput] = Field(default_factory=list)
    installment_candidates: list[InstallmentCandidateInput] = Field(default_factory=list)
    reconciliation: Optional[ReconciliationInput] = None
    findings: list[ValidationFinding] = Field(default_factory=list)
    options: Optional[ValidationOptions] = None


class NormalizedTransactionRecord(BaseModel):
    record_id: str
    source_candidate_id: str
    transaction_date: Optional[str] = None
    posted_date: Optional[str] = None
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
    field_label: Optional[str] = None
    value_type: str = "text"
    value: str
    currency: Optional[str] = None
    confidence: float
    source: Optional[SourceReference] = None
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class ValidatedEntity(BaseModel):
    entity_id: str
    entity_type: str
    value: str
    source: Optional[SourceReference] = None
    confidence: float
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class ValidatedReference(BaseModel):
    reference_id: str
    reference_type: str
    value: str
    masked: bool
    source: Optional[SourceReference] = None
    confidence: float
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class ValidatedLineItem(BaseModel):
    line_item_id: str
    description: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class NormalizedInstallmentRecord(BaseModel):
    installment_id: str
    purchase_date: Optional[str] = None
    posted_date: Optional[str] = None
    description: str
    principal_amount: Optional[float] = None
    current_billing_amount: Optional[float] = None
    remaining_balance: Optional[float] = None
    currency: str
    term_text: Optional[str] = None
    source: Optional[SourceReference] = None
    confidence: float
    quality_status: str
    reason_codes: list[str] = Field(default_factory=list)


class ReviewItem(BaseModel):
    review_id: str
    item_type: str
    severity: str = "warning"
    title: str
    message: str
    record_id: Optional[str] = None
    field_name: Optional[str] = None
    source: Optional[SourceReference] = None
    reason_codes: list[str] = Field(default_factory=list)
    recommended_action: str = "review"


class ValidationSummary(BaseModel):
    input_transaction_candidate_count: int
    normalized_record_count: int
    valid_record_count: int
    warning_record_count: int
    invalid_record_count: int
    duplicate_record_count: int
    financial_field_count: int
    section_candidate_count: int = 0
    entity_count: int = 0
    reference_count: int = 0
    line_item_count: int = 0
    installment_count: int = 0
    warning_installment_count: int = 0
    invalid_installment_count: int = 0
    debit_total: float
    credit_total: float
    net_total: float
    review_item_count: int = 0
    document_review_status: str = "ready"
    recommended_action: str = "save_ready_transactions"
    reconciliation_delta: Optional[float] = None


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
    section_candidates: list[SectionCandidateInput] = Field(default_factory=list)
    validated_entities: list[ValidatedEntity] = Field(default_factory=list)
    validated_references: list[ValidatedReference] = Field(default_factory=list)
    validated_line_items: list[ValidatedLineItem] = Field(default_factory=list)
    normalized_installments: list[NormalizedInstallmentRecord] = Field(default_factory=list)
    document_financial_summary: dict[str, str] = Field(default_factory=dict)
    review_items: list[ReviewItem] = Field(default_factory=list)
    summary: ValidationSummary
    evaluation: ValidationEvaluation
    findings: list[ValidationFinding] = Field(default_factory=list)
