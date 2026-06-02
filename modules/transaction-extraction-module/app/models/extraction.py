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


class ParsedOcrWordBlock(BaseModel):
    page_number: int
    text: str
    confidence: Optional[float] = None
    x: float
    y: float
    width: float
    height: float


class ParsedPageText(BaseModel):
    page_number: int
    text: str
    ocr_word_blocks: list[ParsedOcrWordBlock] = Field(default_factory=list)


class ParsedClassification(BaseModel):
    document_type: str = "unknown"
    document_subtype: str = "unknown"
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
    enable_line_items: Optional[bool] = None


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
    section_id: Optional[str] = None
    section_label: Optional[str] = None
    source_text_redacted: Optional[str] = None
    ocr_confidence: Optional[float] = None
    extraction_confidence: Optional[float] = None


class TransactionCandidate(BaseModel):
    candidate_id: str
    date_text: Optional[str] = None
    posted_date_text: Optional[str] = None
    description: str
    amount: float
    currency: str
    direction: str
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class FinancialFieldCandidate(BaseModel):
    field_name: str
    field_label: Optional[str] = None
    value_type: str = "text"
    value_text: str
    normalized_value: Optional[str] = None
    currency: Optional[str] = None
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class SectionCandidate(BaseModel):
    section_id: str
    section_label: str
    page_number: Optional[int] = None
    first_line_number: int
    last_line_number: int
    source_text_redacted: str
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class EntityCandidate(BaseModel):
    entity_id: str
    entity_type: str
    value_text: str
    normalized_value: Optional[str] = None
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class ReferenceCandidate(BaseModel):
    reference_id: str
    reference_type: str
    value_text: str
    normalized_value: Optional[str] = None
    masked: bool = False
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class LineItemCandidate(BaseModel):
    line_item_id: str
    description: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    source: SourceReference
    confidence: float
    reason_codes: list[str] = Field(default_factory=list)


class QualityMetadata(BaseModel):
    text_length: int
    pages_processed: int
    low_text_input: bool = False
    upstream_finding_codes: list[str] = Field(default_factory=list)


class ReconciliationResult(BaseModel):
    status: str = "not_available"
    previous_balance: Optional[float] = None
    debit_total: Optional[float] = None
    credit_total: Optional[float] = None
    total_due: Optional[float] = None
    computed_total_due: Optional[float] = None
    difference: Optional[float] = None
    reason_codes: list[str] = Field(default_factory=list)


class ExtractedTableRow(BaseModel):
    values: dict[str, object]
    status: str = "extracted"
    confidence: Optional[float] = None
    source: Optional[SourceReference] = None


class ExtractedTable(BaseModel):
    table_id: str
    title: str
    columns: list[str]
    rows: list[ExtractedTableRow] = Field(default_factory=list)


class ExtractionSummary(BaseModel):
    transaction_candidate_count: int
    financial_field_candidate_count: int
    section_candidate_count: int = 0
    entity_candidate_count: int = 0
    reference_candidate_count: int = 0
    line_item_candidate_count: int = 0
    debit_total: float
    credit_total: float
    amount_total: float
    pages_processed: int
    text_length: int
    low_confidence_candidate_count: int
    reconciliation_status: str = "not_available"


class ExtractionEvaluation(BaseModel):
    extraction_id: str
    parse_id: Optional[str] = None
    document_type: str
    status: ExtractionStatus
    transaction_candidate_count: int
    financial_field_candidate_count: int
    section_candidate_count: int = 0
    entity_candidate_count: int = 0
    reference_candidate_count: int = 0
    line_item_candidate_count: int = 0
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
    section_candidates: list[SectionCandidate] = Field(default_factory=list)
    entity_candidates: list[EntityCandidate] = Field(default_factory=list)
    reference_candidates: list[ReferenceCandidate] = Field(default_factory=list)
    line_item_candidates: list[LineItemCandidate] = Field(default_factory=list)
    quality_metadata: Optional[QualityMetadata] = None
    reconciliation: Optional[ReconciliationResult] = None
    document_tables: list[ExtractedTable] = Field(default_factory=list)
    summary: ExtractionSummary
    evaluation: ExtractionEvaluation
    findings: list[ExtractionFinding] = Field(default_factory=list)
