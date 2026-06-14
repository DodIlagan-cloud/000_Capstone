"""M8 - Data Validation Module Start
Cleans, validates, and deduplicates M7 transaction extraction candidates.
M8 End"""

import re
import uuid
from collections import Counter
from datetime import datetime

from app.config import settings
from app.models.validation import (
    DataValidationRequest,
    DataValidationResult,
    InstallmentCandidateInput,
    NormalizedFinancialField,
    NormalizedInstallmentRecord,
    NormalizedTransactionRecord,
    ReviewItem,
    ValidatedEntity,
    ValidatedLineItem,
    ValidatedReference,
    ValidationEvaluation,
    ValidationFinding,
    ValidationStatus,
    ValidationSummary,
)


MONTH_FORMATS = (
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m/%d/%y",
    "%d/%m/%y",
    "%b %d %Y",
    "%b %d, %Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%d %b %Y",
    "%d %B %Y",
)
SPACE_PATTERN = re.compile(r"\s+")
NON_KEY_PATTERN = re.compile(r"[^a-z0-9]+")
NON_TRANSACTION_SECTIONS = {
    "statement_summary",
    "fees_or_interest",
    "rewards_or_points",
    "unknown_financial_block",
}
OCR_REPAIR_REASON_CODES = {
    "SIDE_COLUMN_TEXT_EXCLUDED",
}
# Known OCR prefix-damage patterns that should route a row to review, not auto-correct text.
OCR_SUSPICIOUS_PREFIX_PATTERNS = (
    re.compile(r"^[I1]ang\b", re.IGNORECASE),
)


def validate_data(request: DataValidationRequest) -> DataValidationResult:
    validation_id = f"validate_{uuid.uuid4().hex[:16]}"
    findings: list[ValidationFinding] = list(request.findings)
    min_confidence = _option_min_confidence(request)
    duplicate_detection_enabled = _option_bool(
        request,
        "enable_duplicate_detection",
        settings.enable_duplicate_detection,
    )
    require_date = _option_bool(request, "require_transaction_date", settings.require_transaction_date)
    require_direction = _option_bool(
        request,
        "require_transaction_direction",
        settings.require_transaction_direction,
    )

    if (
        not request.transaction_candidates
        and not request.financial_field_candidates
        and not request.section_candidates
        and not request.entity_candidates
        and not request.reference_candidates
        and not request.line_item_candidates
        and not request.installment_candidates
    ):
        findings.append(
            ValidationFinding(
                code="MISSING_CANDIDATES",
                severity="error",
                message="At least one extraction candidate is required for validation.",
            )
        )
        return _result(
            validation_id=validation_id,
            request=request,
            status=ValidationStatus.failed,
            records=[],
            fields=[],
            entities=[],
            references=[],
            line_items=[],
            installments=[],
            findings=findings,
            min_confidence=min_confidence,
            duplicate_detection_enabled=duplicate_detection_enabled,
        )

    records = []
    for candidate in request.transaction_candidates[: settings.max_records_per_request]:
        records.append(
            _normalize_transaction_candidate(
                candidate=candidate,
                request=request,
                min_confidence=min_confidence,
                require_date=require_date,
                require_direction=require_direction,
                findings=findings,
            )
        )

    if len(request.transaction_candidates) > settings.max_records_per_request:
        findings.append(
            ValidationFinding(
                code="RECORD_LIMIT_APPLIED",
                severity="warning",
                message="Only the configured maximum number of transaction candidates was validated.",
            )
        )

    if duplicate_detection_enabled:
        _mark_duplicates(records, findings)

    _apply_ocr_review_gates(records, findings)

    require_section_context = bool(request.section_candidates)
    fields = [
        _normalize_field(candidate, min_confidence, findings, require_section_context)
        for candidate in request.financial_field_candidates
    ]
    entities = [_normalize_entity(candidate, min_confidence, findings) for candidate in request.entity_candidates]
    references = [_normalize_reference(candidate, min_confidence, findings) for candidate in request.reference_candidates]
    line_items = [_normalize_line_item(candidate, min_confidence, findings) for candidate in request.line_item_candidates]
    installments = [_normalize_installment(candidate, min_confidence, findings) for candidate in request.installment_candidates]
    if request.reconciliation and request.reconciliation.status == "needs_review":
        findings.append(
            ValidationFinding(
                code="DOCUMENT_RECONCILIATION_REVIEW",
                severity="warning",
                message="Statement summary and extracted transactions do not reconcile.",
            )
        )

    status = ValidationStatus.completed_with_warnings if findings else ValidationStatus.completed
    if any(finding.severity == "error" for finding in findings):
        status = ValidationStatus.completed_with_warnings if records or fields else ValidationStatus.failed

    return _result(
        validation_id=validation_id,
        request=request,
        status=status,
        records=records,
        fields=fields,
        entities=entities,
        references=references,
        line_items=line_items,
        installments=installments,
        findings=findings,
        min_confidence=min_confidence,
        duplicate_detection_enabled=duplicate_detection_enabled,
    )


def _normalize_transaction_candidate(
    candidate,
    request: DataValidationRequest,
    min_confidence: float,
    require_date: bool,
    require_direction: bool,
    findings: list[ValidationFinding],
) -> NormalizedTransactionRecord:
    reason_codes = list(candidate.reason_codes)
    normalized_date = _normalize_date(candidate.date_text)
    normalized_posted_date = _normalize_date(candidate.posted_date_text)
    description = _normalize_description(candidate.description)
    currency = (candidate.currency or settings.default_currency).upper()
    direction = _normalize_direction(candidate.direction)
    amount = round(abs(candidate.amount), 2)

    if not normalized_date and require_date:
        reason_codes.append("MISSING_TRANSACTION_DATE")
        findings.append(
            ValidationFinding(
                code="MISSING_TRANSACTION_DATE",
                severity="warning",
                message="Transaction candidate does not include a usable transaction date.",
                record_id=candidate.candidate_id,
            )
        )

    if not description:
        reason_codes.append("MISSING_DESCRIPTION")
        findings.append(
            ValidationFinding(
                code="MISSING_DESCRIPTION",
                severity="warning",
                message="Transaction candidate does not include a usable description.",
                record_id=candidate.candidate_id,
            )
        )

    if amount <= 0:
        reason_codes.append("INVALID_AMOUNT")
        findings.append(
            ValidationFinding(
                code="INVALID_AMOUNT",
                severity="warning",
                message="Transaction candidate amount must be greater than zero.",
                record_id=candidate.candidate_id,
            )
        )

    if direction == "unknown" and require_direction:
        reason_codes.append("UNKNOWN_DIRECTION")
        findings.append(
            ValidationFinding(
                code="UNKNOWN_DIRECTION",
                severity="warning",
                message="Transaction candidate direction could not be validated.",
                record_id=candidate.candidate_id,
            )
        )

    section_label = (candidate.source.section_label if candidate.source else None) or ""
    if section_label in NON_TRANSACTION_SECTIONS:
        reason_codes.append("NON_TRANSACTION_SECTION")
        findings.append(
            ValidationFinding(
                code="NON_TRANSACTION_SECTION",
                severity="warning",
                message="Transaction candidate came from a non-transaction source section and requires review.",
                record_id=candidate.candidate_id,
            )
        )

    if candidate.confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_RECORD")
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_RECORD",
                severity="warning",
                message="Transaction candidate confidence is below the configured validation threshold.",
                record_id=candidate.candidate_id,
            )
        )

    if _low_confidence_amount(candidate, min_confidence):
        reason_codes.append("LOW_CONFIDENCE_AMOUNT")
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_AMOUNT",
                severity="warning",
                message="Transaction amount was read with low OCR confidence and should be checked.",
                record_id=f"record_{candidate.candidate_id}",
            )
        )

    required_field_reason_codes = _required_save_field_reason_codes(request, candidate, min_confidence, findings)
    classification_reason_codes = _classification_review_reason_codes(candidate, min_confidence, findings)
    reason_codes.extend(required_field_reason_codes)
    reason_codes.extend(classification_reason_codes)

    quality_status = "valid"
    if any(
        code in reason_codes
        for code in [
            "INVALID_AMOUNT",
            "MISSING_DESCRIPTION",
            "UNKNOWN_DOCUMENT_TYPE",
        ]
    ):
        quality_status = "invalid"
    elif any(
        code in reason_codes
        for code in [
            "MISSING_TRANSACTION_DATE",
            "UNKNOWN_DIRECTION",
            "LOW_CONFIDENCE_RECORD",
            "LOW_CONFIDENCE_AMOUNT",
            "LOW_CONFIDENCE_DOCUMENT_TYPE",
            "UNKNOWN_TRANSACTION_TYPE",
            "LOW_CONFIDENCE_TRANSACTION_TYPE",
            "UNKNOWN_SPENDING_CATEGORY",
            "LOW_CONFIDENCE_SPENDING_CATEGORY",
            "AMBIGUOUS_DOCUMENT_TYPE",
            "AMBIGUOUS_TRANSACTION_TYPE",
            "AMBIGUOUS_SPENDING_CATEGORY",
            "AI_CLASSIFICATION_REVIEW_REQUIRED",
            "AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED",
            "RULE_AI_TRANSACTION_TYPE_CONFLICT",
            "RULE_AI_SPENDING_CATEGORY_CONFLICT",
            "PENDING_RECOGNITION_LABEL_SUGGESTION",
            "UNAPPROVED_RECOGNITION_LABEL",
            "REJECTED_RECOGNITION_LABEL_SUGGESTION",
        ]
    ):
        quality_status = "warning"
    elif "NON_TRANSACTION_SECTION" in reason_codes:
        quality_status = "warning"

    return NormalizedTransactionRecord(
        record_id=f"record_{candidate.candidate_id}",
        source_candidate_id=candidate.candidate_id,
        transaction_date=normalized_date,
        posted_date=normalized_posted_date,
        description=description,
        amount=amount,
        currency=currency,
        direction=direction,
        signed_amount=_signed_amount(amount, direction),
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
        transaction_type=candidate.transaction_type.strip().lower() or "unknown",
        transaction_subtype=candidate.transaction_subtype.strip().lower() or "unknown",
        transaction_type_confidence=round(candidate.transaction_type_confidence, 3),
        transaction_type_status=candidate.transaction_type_status.strip().lower() or "unknown",
        transaction_type_reason_codes=list(candidate.transaction_type_reason_codes),
        transaction_type_scores=dict(candidate.transaction_type_scores),
        spending_category=candidate.spending_category.strip().lower() or "uncategorized",
        spending_subcategory=candidate.spending_subcategory.strip().lower() or "unknown",
        spending_category_confidence=round(candidate.spending_category_confidence, 3),
        spending_category_status=candidate.spending_category_status.strip().lower() or "unknown",
        spending_category_reason_codes=list(candidate.spending_category_reason_codes),
        spending_category_scores=dict(candidate.spending_category_scores),
        classification_source=candidate.classification_source.strip().lower() or "unknown",
        ai_model_name=candidate.ai_model_name,
        ai_model_version=candidate.ai_model_version,
        ai_confidence=round(candidate.ai_confidence, 3) if candidate.ai_confidence is not None else None,
        classification_review_required=candidate.classification_review_required,
        classification_review_reason_codes=list(candidate.classification_review_reason_codes),
        recognition_suggestion_id=candidate.recognition_suggestion_id,
        recognition_suggestion_status=(candidate.recognition_suggestion_status or "none").strip().lower(),
        suggested_transaction_type=_optional_lower(candidate.suggested_transaction_type),
        suggested_transaction_subtype=_optional_lower(candidate.suggested_transaction_subtype),
        suggested_spending_category=_optional_lower(candidate.suggested_spending_category),
        suggested_spending_subcategory=_optional_lower(candidate.suggested_spending_subcategory),
        suggestion_confidence=round(candidate.suggestion_confidence, 3) if candidate.suggestion_confidence is not None else None,
        suggestion_reason_codes=list(candidate.suggestion_reason_codes),
        suggestion_source=_optional_lower(candidate.suggestion_source),
        suggestion_evidence_ref=candidate.suggestion_evidence_ref,
        classification_vocabulary_status=(candidate.classification_vocabulary_status or "active_vocabulary_match").strip().lower(),
        recognition_context_version=candidate.recognition_context_version,
        classification_confirmation_mode=_optional_lower(candidate.classification_confirmation_mode),
        classification_human_confirmed=bool(candidate.classification_human_confirmed),
    )


def _normalize_field(
    candidate,
    min_confidence: float,
    findings: list[ValidationFinding],
    require_section_context: bool,
) -> NormalizedFinancialField:
    reason_codes = list(candidate.reason_codes)
    value = (candidate.normalized_value or candidate.value_text).strip()
    quality_status = "valid"
    if require_section_context and not (candidate.source and candidate.source.section_label):
        reason_codes.append("MISSING_SECTION_CONTEXT")
        quality_status = "warning"
        findings.append(
            ValidationFinding(
                code="MISSING_SECTION_CONTEXT",
                severity="warning",
                message="Financial field does not include source-section context.",
            )
        )
    if candidate.confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_FIELD")
        quality_status = "warning"
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_FIELD",
                severity="warning",
                message="Financial field confidence is below the configured validation threshold.",
            )
        )
    if not value:
        reason_codes.append("MISSING_FIELD_VALUE")
        quality_status = "invalid"
        findings.append(
            ValidationFinding(
                code="MISSING_FIELD_VALUE",
                severity="warning",
                message="Financial field does not include a usable value.",
            )
        )

    return NormalizedFinancialField(
        field_name=candidate.field_name.strip().lower(),
        field_label=candidate.field_label,
        value_type=candidate.value_type,
        value=value,
        currency=(candidate.currency.upper() if candidate.currency else None),
        confidence=round(candidate.confidence, 3),
        source=candidate.source,
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _normalize_entity(candidate, min_confidence: float, findings: list[ValidationFinding]) -> ValidatedEntity:
    reason_codes = list(candidate.reason_codes)
    value = (candidate.normalized_value or candidate.value_text).strip()
    quality_status = _candidate_quality(candidate.confidence, min_confidence, reason_codes, "LOW_CONFIDENCE_ENTITY")
    if quality_status == "warning":
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_ENTITY",
                severity="warning",
                message="Entity candidate confidence is below the configured validation threshold.",
            )
        )
    return ValidatedEntity(
        entity_id=candidate.entity_id,
        entity_type=candidate.entity_type.strip().lower(),
        value=value,
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _normalize_reference(candidate, min_confidence: float, findings: list[ValidationFinding]) -> ValidatedReference:
    reason_codes = list(candidate.reason_codes)
    value = (candidate.normalized_value or candidate.value_text).strip()
    quality_status = _candidate_quality(candidate.confidence, min_confidence, reason_codes, "LOW_CONFIDENCE_REFERENCE")
    if quality_status == "warning":
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_REFERENCE",
                severity="warning",
                message="Reference candidate confidence is below the configured validation threshold.",
            )
        )
    if _looks_unmasked_sensitive(value, candidate.masked):
        reason_codes.append("UNMASKED_SENSITIVE_REFERENCE")
        quality_status = "warning"
        findings.append(
            ValidationFinding(
                code="UNMASKED_SENSITIVE_REFERENCE",
                severity="warning",
                message="Reference candidate appears to contain sensitive digits without masking.",
            )
        )
    return ValidatedReference(
        reference_id=candidate.reference_id,
        reference_type=candidate.reference_type.strip().lower(),
        value=value,
        masked=candidate.masked,
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _normalize_line_item(candidate, min_confidence: float, findings: list[ValidationFinding]) -> ValidatedLineItem:
    reason_codes = list(candidate.reason_codes)
    quality_status = _candidate_quality(candidate.confidence, min_confidence, reason_codes)
    return ValidatedLineItem(
        line_item_id=candidate.line_item_id,
        description=_normalize_description(candidate.description),
        amount=round(abs(candidate.amount), 2) if candidate.amount is not None else None,
        currency=(candidate.currency or settings.default_currency).upper() if candidate.amount is not None else candidate.currency,
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _normalize_installment(
    candidate: InstallmentCandidateInput,
    min_confidence: float,
    findings: list[ValidationFinding],
) -> NormalizedInstallmentRecord:
    reason_codes = list(candidate.reason_codes)
    description = _normalize_description(candidate.description)
    purchase_date = _normalize_date(candidate.purchase_date_text)
    posted_date = _normalize_date(candidate.posted_date_text)
    principal_amount = round(abs(candidate.principal_amount), 2) if candidate.principal_amount is not None else None
    current_billing_amount = round(abs(candidate.current_billing_amount), 2) if candidate.current_billing_amount is not None else None
    remaining_balance = round(abs(candidate.remaining_balance), 2) if candidate.remaining_balance is not None else None
    currency = (candidate.currency or settings.default_currency).upper()
    quality_status = "valid"

    if not description:
        reason_codes.append("MISSING_INSTALLMENT_DESCRIPTION")
        quality_status = "invalid"
        findings.append(
            ValidationFinding(
                code="MISSING_INSTALLMENT_DESCRIPTION",
                severity="warning",
                message="Installment candidate does not include a usable description.",
                record_id=candidate.installment_id,
            )
        )
    if principal_amount is None and current_billing_amount is None and remaining_balance is None:
        reason_codes.append("MISSING_INSTALLMENT_AMOUNT")
        quality_status = "invalid"
        findings.append(
            ValidationFinding(
                code="MISSING_INSTALLMENT_AMOUNT",
                severity="warning",
                message="Installment candidate does not include a usable amount.",
                record_id=candidate.installment_id,
            )
        )
    if not candidate.term_text:
        reason_codes.append("MISSING_INSTALLMENT_TERM")
        quality_status = "warning" if quality_status == "valid" else quality_status
        findings.append(
            ValidationFinding(
                code="MISSING_INSTALLMENT_TERM",
                severity="warning",
                message="Installment term or progress is missing and should be reviewed.",
                record_id=candidate.installment_id,
            )
        )
    if candidate.confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_INSTALLMENT")
        quality_status = "warning" if quality_status == "valid" else quality_status
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_INSTALLMENT",
                severity="warning",
                message="Installment candidate confidence is below the configured validation threshold.",
                record_id=candidate.installment_id,
            )
        )

    return NormalizedInstallmentRecord(
        installment_id=candidate.installment_id,
        purchase_date=purchase_date,
        posted_date=posted_date,
        description=description,
        principal_amount=principal_amount,
        current_billing_amount=current_billing_amount,
        remaining_balance=remaining_balance,
        currency=currency,
        term_text=candidate.term_text,
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _mark_duplicates(records: list[NormalizedTransactionRecord], findings: list[ValidationFinding]) -> None:
    seen: dict[tuple[object, ...], str] = {}
    for record in records:
        key = (
            record.transaction_date,
            _dedupe_text(record.description),
            round(record.amount / settings.duplicate_match_amount_tolerance),
            record.currency,
            record.direction,
        )
        if key in seen:
            record.duplicate_of = seen[key]
            record.quality_status = "warning" if record.quality_status == "valid" else record.quality_status
            record.reason_codes.append("DUPLICATE_TRANSACTION")
            findings.append(
                ValidationFinding(
                    code="DUPLICATE_TRANSACTION",
                    severity="warning",
                    message="Transaction candidate appears to duplicate an earlier normalized record.",
                    record_id=record.record_id,
                )
            )
        else:
            seen[key] = record.record_id


def _low_confidence_amount(candidate, min_confidence: float) -> bool:
    if not candidate.source or candidate.source.ocr_confidence is None:
        return False
    if "OCR_LAYOUT_ROW_RECONSTRUCTED" not in candidate.reason_codes:
        return False
    return candidate.source.ocr_confidence < min_confidence


def _required_save_field_reason_codes(
    request: DataValidationRequest,
    candidate,
    min_confidence: float,
    findings: list[ValidationFinding],
) -> list[str]:
    reason_codes: list[str] = []
    record_id = f"record_{candidate.candidate_id}"
    document_type = (request.document_type or "unknown").strip().lower()
    document_status = (request.document_type_status or "unknown").strip().lower()

    if document_type == "unknown":
        reason_codes.append("UNKNOWN_DOCUMENT_TYPE")
        findings.append(
            ValidationFinding(
                code="UNKNOWN_DOCUMENT_TYPE",
                severity="error",
                message="Document type is required before this transaction can be saved.",
                record_id=record_id,
            )
        )
    elif document_status == "ambiguous":
        reason_codes.append("AMBIGUOUS_DOCUMENT_TYPE")
        findings.append(
            ValidationFinding(
                code="AMBIGUOUS_DOCUMENT_TYPE",
                severity="warning",
                message="Document type classification has ambiguous signals and should be reviewed.",
                record_id=record_id,
            )
        )
    elif request.document_type_confidence is not None and request.document_type_confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_DOCUMENT_TYPE")
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_DOCUMENT_TYPE",
                severity="warning",
                message="Document type classification confidence is below the configured threshold.",
                record_id=record_id,
            )
        )

    return reason_codes


def _classification_review_reason_codes(candidate, min_confidence: float, findings: list[ValidationFinding]) -> list[str]:
    reason_codes: list[str] = []
    record_id = f"record_{candidate.candidate_id}"
    transaction_status = (candidate.transaction_type_status or "unknown").lower()
    category_status = (candidate.spending_category_status or "unknown").lower()
    transaction_type = (candidate.transaction_type or "unknown").lower()
    spending_category = (candidate.spending_category or "uncategorized").lower()

    if transaction_type == "unknown" or transaction_status == "unknown":
        reason_codes.append("UNKNOWN_TRANSACTION_TYPE")
        findings.append(
            ValidationFinding(
                code="UNKNOWN_TRANSACTION_TYPE",
                severity="warning",
                message="Transaction type classification could not be determined.",
                record_id=record_id,
            )
        )
    elif transaction_status == "ambiguous":
        reason_codes.append("AMBIGUOUS_TRANSACTION_TYPE")
        findings.append(
            ValidationFinding(
                code="AMBIGUOUS_TRANSACTION_TYPE",
                severity="warning",
                message="Transaction type classification has ambiguous signals.",
                record_id=record_id,
            )
        )
    elif candidate.transaction_type_confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_TRANSACTION_TYPE")
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_TRANSACTION_TYPE",
                severity="warning",
                message="Transaction type classification confidence is below the configured threshold.",
                record_id=record_id,
            )
        )

    if spending_category == "uncategorized" or category_status == "unknown":
        reason_codes.append("UNKNOWN_SPENDING_CATEGORY")
        findings.append(
            ValidationFinding(
                code="UNKNOWN_SPENDING_CATEGORY",
                severity="warning",
                message="Spending category classification could not be determined.",
                record_id=record_id,
            )
        )
    elif category_status == "ambiguous":
        reason_codes.append("AMBIGUOUS_SPENDING_CATEGORY")
        findings.append(
            ValidationFinding(
                code="AMBIGUOUS_SPENDING_CATEGORY",
                severity="warning",
                message="Spending category classification has ambiguous signals.",
                record_id=record_id,
            )
        )
    elif candidate.spending_category_confidence < min_confidence:
        reason_codes.append("LOW_CONFIDENCE_SPENDING_CATEGORY")
        findings.append(
            ValidationFinding(
                code="LOW_CONFIDENCE_SPENDING_CATEGORY",
                severity="warning",
                message="Spending category classification confidence is below the configured threshold.",
                record_id=record_id,
            )
        )

    if candidate.classification_review_required:
        review_codes = list(candidate.classification_review_reason_codes) or ["AI_CLASSIFICATION_REVIEW_REQUIRED"]
        for review_code in review_codes:
            if review_code not in reason_codes:
                reason_codes.append(review_code)
        findings.append(
            ValidationFinding(
                code="AI_CLASSIFICATION_REVIEW_REQUIRED",
                severity="warning",
                message="AI-assisted transaction classification requires review.",
                record_id=record_id,
            )
        )

    suggestion_status = (candidate.recognition_suggestion_status or "none").lower()
    vocabulary_status = (candidate.classification_vocabulary_status or "active_vocabulary_match").lower()
    suggestion_source = (candidate.suggestion_source or "").lower()
    if vocabulary_status == "outside_vocabulary_proposal" and suggestion_source == "ai":
        reason_codes.append("AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED")
        findings.append(
            ValidationFinding(
                code="AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED",
                severity="warning",
                message="AI suggested a new transaction or spending classification that must be accepted or edited before save.",
                record_id=record_id,
            )
        )
    if suggestion_status in {"rejected", "invalid"}:
        reason_codes.append("REJECTED_RECOGNITION_LABEL_SUGGESTION")
        findings.append(
            ValidationFinding(
                code="REJECTED_RECOGNITION_LABEL_SUGGESTION",
                severity="warning",
                message="A proposed transaction or spending label was rejected or marked unusable.",
                record_id=record_id,
            )
        )
    elif suggestion_status in {"unapproved", "outside_vocabulary"}:
        reason_codes.append("UNAPPROVED_RECOGNITION_LABEL")
        findings.append(
            ValidationFinding(
                code="UNAPPROVED_RECOGNITION_LABEL",
                severity="warning",
                message="A transaction or spending label is outside the approved recognition settings.",
                record_id=record_id,
            )
        )
    elif candidate.recognition_suggestion_id or suggestion_status in {"pending", "proposed"}:
        reason_codes.append("PENDING_RECOGNITION_LABEL_SUGGESTION")
        findings.append(
            ValidationFinding(
                code="PENDING_RECOGNITION_LABEL_SUGGESTION",
                severity="warning",
                message="A proposed transaction or spending label is waiting for administrator review.",
                record_id=record_id,
            )
        )

    return reason_codes


def _optional_lower(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    return normalized or None


def _apply_ocr_review_gates(records: list[NormalizedTransactionRecord], findings: list[ValidationFinding]) -> None:
    for record in records:
        if OCR_REPAIR_REASON_CODES.intersection(record.reason_codes):
            _mark_record_warning(record, "OCR_REPAIR_REVIEW")
            findings.append(
                ValidationFinding(
                    code="OCR_REPAIR_REVIEW",
                    severity="warning",
                    message="Transaction text was repaired from OCR layout evidence and should be reviewed.",
                    record_id=record.record_id,
                )
            )
        if _looks_like_suspicious_ocr_description(record.description):
            _mark_record_warning(record, "SUSPICIOUS_OCR_TEXT")
            findings.append(
                ValidationFinding(
                    code="SUSPICIOUS_OCR_TEXT",
                    severity="warning",
                    message="Transaction description may contain OCR text damage.",
                    record_id=record.record_id,
                )
            )


def _mark_record_warning(record: NormalizedTransactionRecord, reason_code: str) -> None:
    if reason_code not in record.reason_codes:
        record.reason_codes.append(reason_code)
    if record.quality_status == "valid":
        record.quality_status = "warning"


def _looks_like_suspicious_ocr_description(description: str) -> bool:
    words = description.split()
    if not words:
        return True
    first_token = re.sub(r"[^A-Za-z0-9]", "", words[0])
    if len(first_token) <= 1:
        return True
    if any(pattern.match(description) for pattern in OCR_SUSPICIOUS_PREFIX_PATTERNS):
        return True
    return False


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", raw):
        return raw

    candidates = [raw]
    if "-" in raw:
        candidates.append(raw.replace("-", "/"))
        candidates.append(raw.replace("-", " "))

    for candidate in dict.fromkeys(candidates):
        cleaned = " ".join(candidate.split())
        for date_format in MONTH_FORMATS:
            try:
                return datetime.strptime(cleaned, date_format).date().isoformat()
            except ValueError:
                continue
    return None


def _normalize_description(value: str) -> str:
    return SPACE_PATTERN.sub(" ", value).strip(" -|").title()


def _normalize_direction(value: str) -> str:
    lowered = (value or "").strip().lower()
    return lowered if lowered in {"debit", "credit"} else "unknown"


def _signed_amount(amount: float, direction: str) -> float:
    if direction == "debit":
        return round(-amount, 2)
    if direction == "credit":
        return round(amount, 2)
    return 0.0


def _dedupe_text(value: str) -> str:
    return NON_KEY_PATTERN.sub("", value.lower())


def _candidate_quality(
    confidence: float,
    min_confidence: float,
    reason_codes: list[str],
    low_confidence_code: str = "LOW_CONFIDENCE_FIELD",
) -> str:
    if confidence < min_confidence:
        reason_codes.append(low_confidence_code)
        return "warning"
    return "valid"


def _looks_unmasked_sensitive(value: str, masked: bool) -> bool:
    return not masked and bool(re.search(r"\d{8,}", value))


def _document_financial_summary(fields: list[NormalizedFinancialField]) -> dict[str, str]:
    # Transaction-table values stay with normalized records; this summary is for document-level facts.
    return {
        field.field_name: field.value
        for field in fields
        if field.source and field.source.section_label != "transaction_table"
    }


def _option_min_confidence(request: DataValidationRequest) -> float:
    if request.options and request.options.min_confidence is not None:
        return request.options.min_confidence
    return settings.min_record_confidence


def _option_bool(request: DataValidationRequest, name: str, default: bool) -> bool:
    if not request.options:
        return default
    value = getattr(request.options, name)
    return default if value is None else value


def _result(
    validation_id: str,
    request: DataValidationRequest,
    status: ValidationStatus,
    records: list[NormalizedTransactionRecord],
    fields: list[NormalizedFinancialField],
    entities: list[ValidatedEntity],
    references: list[ValidatedReference],
    line_items: list[ValidatedLineItem],
    installments: list[NormalizedInstallmentRecord],
    findings: list[ValidationFinding],
    min_confidence: float,
    duplicate_detection_enabled: bool,
) -> DataValidationResult:
    valid_records = [record for record in records if record.quality_status == "valid"]
    warning_records = [record for record in records if record.quality_status == "warning"]
    invalid_records = [record for record in records if record.quality_status == "invalid"]
    warning_installments = [installment for installment in installments if installment.quality_status == "warning"]
    invalid_installments = [installment for installment in installments if installment.quality_status == "invalid"]
    duplicates = [record for record in records if record.duplicate_of]
    review_items = _build_review_items(request, records, installments, findings)
    finding_counts = dict(Counter(finding.code for finding in findings))
    reconciliation_delta = request.reconciliation.difference if request.reconciliation else None
    document_review_status = _document_review_status(review_items, invalid_records, invalid_installments)
    recommended_action = _recommended_action(document_review_status, valid_records, review_items)
    debit_total = round(sum(record.amount for record in records if record.direction == "debit"), 2)
    credit_total = round(sum(record.amount for record in records if record.direction == "credit"), 2)
    net_total = round(sum(record.signed_amount for record in records), 2)

    summary = ValidationSummary(
        input_transaction_candidate_count=len(request.transaction_candidates),
        normalized_record_count=len(records),
        valid_record_count=len(valid_records),
        warning_record_count=len(warning_records),
        invalid_record_count=len(invalid_records),
        duplicate_record_count=len(duplicates),
        financial_field_count=len(fields),
        section_candidate_count=len(request.section_candidates),
        entity_count=len(entities),
        reference_count=len(references),
        line_item_count=len(line_items),
        installment_count=len(installments),
        warning_installment_count=len(warning_installments),
        invalid_installment_count=len(invalid_installments),
        debit_total=debit_total,
        credit_total=credit_total,
        net_total=net_total,
        review_item_count=len(review_items),
        document_review_status=document_review_status,
        recommended_action=recommended_action,
        reconciliation_delta=reconciliation_delta,
    )
    evaluation = ValidationEvaluation(
        validation_id=validation_id,
        extraction_id=request.extraction_id,
        parse_id=request.parse_id,
        document_type=request.document_type,
        status=status,
        finding_counts=finding_counts,
        min_confidence=min_confidence,
        duplicate_detection_enabled=duplicate_detection_enabled,
        normalized_record_count=len(records),
        valid_record_count=len(valid_records),
    )

    return DataValidationResult(
        validation_id=validation_id,
        status=status,
        extraction_id=request.extraction_id,
        parse_id=request.parse_id,
        document=request.document,
        document_type=request.document_type,
        document_recognition_suggestion_id=request.document_recognition_suggestion_id,
        document_recognition_suggestion_status=(request.document_recognition_suggestion_status or "none").strip().lower(),
        suggested_document_type=_optional_lower(request.suggested_document_type),
        suggested_document_subtype=_optional_lower(request.suggested_document_subtype),
        document_suggestion_confidence=round(request.document_suggestion_confidence, 3)
        if request.document_suggestion_confidence is not None
        else None,
        document_suggestion_reason_codes=list(request.document_suggestion_reason_codes),
        document_suggestion_source=_optional_lower(request.document_suggestion_source),
        document_suggestion_evidence_ref=request.document_suggestion_evidence_ref,
        normalized_records=records,
        financial_fields=fields,
        section_candidates=request.section_candidates,
        validated_entities=entities,
        validated_references=references,
        validated_line_items=line_items,
        normalized_installments=installments,
        document_financial_summary=_document_financial_summary(fields),
        review_items=review_items,
        summary=summary,
        evaluation=evaluation,
        findings=findings,
    )


def _build_review_items(
    request: DataValidationRequest,
    records: list[NormalizedTransactionRecord],
    installments: list[NormalizedInstallmentRecord],
    findings: list[ValidationFinding],
) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    if request.reconciliation and request.reconciliation.status == "needs_review":
        delta = request.reconciliation.difference
        items.append(
            ReviewItem(
                review_id="review_document_reconciliation",
                item_type="document_reconciliation",
                title="Statement totals do not match",
                message=f"Extracted transactions differ from the document summary by {settings.default_currency} {abs(delta or 0):,.2f}.",
                reason_codes=[*request.reconciliation.reason_codes, "DOCUMENT_RECONCILIATION_REVIEW"],
                recommended_action="review_reconciliation",
            )
        )
    finding_by_record: dict[str, list[ValidationFinding]] = {}
    for finding in findings:
        if finding.record_id:
            finding_by_record.setdefault(finding.record_id, []).append(finding)

    for record in records:
        if record.quality_status == "valid" and not record.duplicate_of:
            continue
        record_findings = finding_by_record.get(record.record_id, [])
        title, message = _record_review_copy(record, record_findings)
        items.append(
            ReviewItem(
                review_id=f"review_{record.record_id}",
                item_type="transaction",
                severity="warning" if record.quality_status != "invalid" else "error",
                title=title,
                message=message,
                record_id=record.record_id,
                source=record.source,
                reason_codes=record.reason_codes,
                recommended_action="edit_or_accept",
            )
        )

    for installment in installments:
        if installment.quality_status == "valid":
            continue
        installment_findings = finding_by_record.get(installment.installment_id, [])
        title, message = _installment_review_copy(installment, installment_findings)
        items.append(
            ReviewItem(
                review_id=f"review_{installment.installment_id}",
                item_type="installment",
                severity="warning" if installment.quality_status != "invalid" else "error",
                title=title,
                message=message,
                record_id=installment.installment_id,
                source=installment.source,
                reason_codes=installment.reason_codes,
                recommended_action="edit_or_accept",
            )
        )

    return items


def _record_review_copy(
    record: NormalizedTransactionRecord,
    record_findings: list[ValidationFinding],
) -> tuple[str, str]:
    reason_codes = set(record.reason_codes)
    if record.duplicate_of:
        return "Possible duplicate", "This transaction matches another row in the current upload."
    if "LOW_CONFIDENCE_AMOUNT" in reason_codes:
        return "Check amount", "Amount was read with low OCR confidence. Check the amount before saving."
    if "SUSPICIOUS_OCR_TEXT" in reason_codes:
        return "Check OCR text", f"Description may be missing characters: {record.description}"
    if "OCR_REPAIR_REVIEW" in reason_codes:
        return "Check repaired transaction", "Stats repaired this row from nearby OCR text."
    if "INVALID_AMOUNT" in reason_codes or "MISSING_DESCRIPTION" in reason_codes:
        return "Fix incomplete transaction", "Required transaction details are missing or invalid."
    if "MISSING_TRANSACTION_DATE" in reason_codes or "UNKNOWN_DIRECTION" in reason_codes:
        return "Check transaction details", "Date or debit/credit direction needs confirmation."
    if record_findings:
        return "Review transaction", record_findings[0].message
    return "Review transaction", "This transaction needs confirmation before saving."


def _installment_review_copy(
    installment: NormalizedInstallmentRecord,
    installment_findings: list[ValidationFinding],
) -> tuple[str, str]:
    reason_codes = set(installment.reason_codes)
    if "MISSING_INSTALLMENT_AMOUNT" in reason_codes or "MISSING_INSTALLMENT_DESCRIPTION" in reason_codes:
        return "Fix installment balance", "Required installment balance details are missing."
    if "MISSING_INSTALLMENT_TERM" in reason_codes:
        return "Check installment term", "Installment term or progress is missing and should be reviewed."
    if "LOW_CONFIDENCE_INSTALLMENT" in reason_codes:
        return "Check installment balance", "Installment balance was extracted with low confidence."
    if installment_findings:
        return "Review installment balance", installment_findings[0].message
    return "Review installment balance", "This installment balance needs confirmation before saving."


def _document_review_status(
    review_items: list[ReviewItem],
    invalid_records: list[NormalizedTransactionRecord],
    invalid_installments: list[NormalizedInstallmentRecord],
) -> str:
    if invalid_records or invalid_installments:
        return "blocked"
    if review_items:
        return "needs_review"
    return "ready"


def _recommended_action(
    document_review_status: str,
    valid_records: list[NormalizedTransactionRecord],
    review_items: list[ReviewItem],
) -> str:
    if document_review_status == "blocked":
        return "fix_blocking_errors"
    if review_items and valid_records:
        return "review_items_before_saving_all"
    if review_items:
        return "review_items"
    return "save_ready_transactions"
