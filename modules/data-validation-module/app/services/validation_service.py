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
    NormalizedFinancialField,
    NormalizedTransactionRecord,
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

    if not request.transaction_candidates and not request.financial_field_candidates:
        findings.append(
            ValidationFinding(
                code="MISSING_CANDIDATES",
                severity="error",
                message="At least one transaction or financial field candidate is required for validation.",
            )
        )
        return _result(
            validation_id=validation_id,
            request=request,
            status=ValidationStatus.failed,
            records=[],
            fields=[],
            findings=findings,
            min_confidence=min_confidence,
            duplicate_detection_enabled=duplicate_detection_enabled,
        )

    records = []
    for candidate in request.transaction_candidates[: settings.max_records_per_request]:
        records.append(
            _normalize_transaction_candidate(
                candidate=candidate,
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

    fields = [_normalize_field(candidate, min_confidence, findings) for candidate in request.financial_field_candidates]

    status = ValidationStatus.completed_with_warnings if findings else ValidationStatus.completed
    if any(finding.severity == "error" for finding in findings):
        status = ValidationStatus.completed_with_warnings if records or fields else ValidationStatus.failed

    return _result(
        validation_id=validation_id,
        request=request,
        status=status,
        records=records,
        fields=fields,
        findings=findings,
        min_confidence=min_confidence,
        duplicate_detection_enabled=duplicate_detection_enabled,
    )


def _normalize_transaction_candidate(
    candidate,
    min_confidence: float,
    require_date: bool,
    require_direction: bool,
    findings: list[ValidationFinding],
) -> NormalizedTransactionRecord:
    reason_codes = list(candidate.reason_codes)
    normalized_date = _normalize_date(candidate.date_text)
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

    quality_status = "valid"
    if any(code in reason_codes for code in ["INVALID_AMOUNT", "MISSING_DESCRIPTION"]):
        quality_status = "invalid"
    elif any(
        code in reason_codes
        for code in ["MISSING_TRANSACTION_DATE", "UNKNOWN_DIRECTION", "LOW_CONFIDENCE_RECORD"]
    ):
        quality_status = "warning"

    return NormalizedTransactionRecord(
        record_id=f"record_{candidate.candidate_id}",
        source_candidate_id=candidate.candidate_id,
        transaction_date=normalized_date,
        description=description,
        amount=amount,
        currency=currency,
        direction=direction,
        signed_amount=_signed_amount(amount, direction),
        source=candidate.source,
        confidence=round(candidate.confidence, 3),
        quality_status=quality_status,
        reason_codes=reason_codes,
    )


def _normalize_field(
    candidate,
    min_confidence: float,
    findings: list[ValidationFinding],
) -> NormalizedFinancialField:
    reason_codes = list(candidate.reason_codes)
    value = (candidate.normalized_value or candidate.value_text).strip()
    quality_status = "valid"
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
        value=value,
        currency=(candidate.currency.upper() if candidate.currency else None),
        confidence=round(candidate.confidence, 3),
        source=candidate.source,
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


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().replace("-", " ")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value.strip()):
        return value.strip()
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
    findings: list[ValidationFinding],
    min_confidence: float,
    duplicate_detection_enabled: bool,
) -> DataValidationResult:
    finding_counts = dict(Counter(finding.code for finding in findings))
    valid_records = [record for record in records if record.quality_status == "valid"]
    warning_records = [record for record in records if record.quality_status == "warning"]
    invalid_records = [record for record in records if record.quality_status == "invalid"]
    duplicates = [record for record in records if record.duplicate_of]
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
        debit_total=debit_total,
        credit_total=credit_total,
        net_total=net_total,
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
        normalized_records=records,
        financial_fields=fields,
        summary=summary,
        evaluation=evaluation,
        findings=findings,
    )
