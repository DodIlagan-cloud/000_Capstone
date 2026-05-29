"""M7 - Transaction Extraction Module Start
Extracts transaction and financial field candidates from parsed document text.
M7 End"""

import re
import uuid
from collections import Counter

from app.config import settings
from app.models.extraction import (
    ExtractionEvaluation,
    ExtractionFinding,
    ExtractionStatus,
    FinancialFieldCandidate,
    SourceReference,
    TransactionCandidate,
    TransactionExtractionRequest,
    TransactionExtractionResult,
    ExtractionSummary,
)


AMOUNT_PATTERN = re.compile(
    r"(?:(PHP|USD|AUD|NZD|NZ\$|\$)\s*)?([+-]?\d{1,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2})|[+-]?\d+(?:\.\s?\d{2}|,\d{2}))",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[-\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[-\s]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
FIELD_PATTERNS = {
    "total_amount_due": re.compile(r"\btotal\s+amount\s+due\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE),
    "minimum_amount_due": re.compile(r"\bminimum\s+amount\s+due\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE),
    "payment_due_date": re.compile(r"\bpayment\s+due\s+date\s+(.+)$", re.IGNORECASE),
    "statement_date": re.compile(r"\bstatement\s+date\s+(.+)$", re.IGNORECASE),
    "transfer_amount": re.compile(r"\btransfer\s+amount\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE),
    "confirmation_number": re.compile(r"\bconfirmation\s+no\.?\s+([A-Z0-9-]+)", re.IGNORECASE),
    "reference_number": re.compile(r"\bre(?:f|ference)\.?\s+no\.?\s+([A-Z0-9-]+)", re.IGNORECASE),
    "invoice_number": re.compile(r"\b(?:tax\s+)?invoice\s+no\.?:?\s+([A-Z0-9-]+)", re.IGNORECASE),
    "receipt_total": re.compile(r"\b(?:tax\s+invoice:\s*)?total\s+(?!GST\b)(?:NZD|NZ\$|\$|PHP\s*)?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE),
    "total_gst": re.compile(r"\btotal\s+GST\s+\$?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE),
    "gst_amount": re.compile(r"\bincludes\s+GST\s+of\s+\$?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE),
    "purchase_amount": re.compile(r"\bpurchase\s+(?:NZD|NZ\$|\$|PHP\s*)?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE),
    "card_receipt_amount": re.compile(r"\bNZ\$\s*([0-9,]+,\d{2})", re.IGNORECASE),
}


def extract_transactions(request: TransactionExtractionRequest) -> TransactionExtractionResult:
    extraction_id = f"extract_{uuid.uuid4().hex[:16]}"
    findings: list[ExtractionFinding] = []
    document_type = _document_type(request)
    min_confidence = _option_min_confidence(request)
    field_enabled = _option_bool(request, "enable_field_extraction", settings.enable_field_extraction)
    rows_enabled = _option_bool(request, "enable_transaction_rows", settings.enable_transaction_rows)

    if document_type not in settings.supported_document_types:
        findings.append(
            ExtractionFinding(
                code="UNSUPPORTED_DOCUMENT_TYPE",
                severity="warning",
                message=f"Document type is not configured for extraction: {document_type}",
            )
        )

    findings.extend(_upstream_quality_findings(request))

    text = request.text or ""
    if not text.strip():
        findings.append(
            ExtractionFinding(
                code="MISSING_TEXT",
                severity="error",
                message="Parsed text is required before transaction extraction can run.",
            )
        )
        return _result(
            extraction_id=extraction_id,
            request=request,
            document_type=document_type,
            status=ExtractionStatus.failed,
            transactions=[],
            fields=[],
            findings=findings,
            min_confidence=min_confidence,
            pages_processed=0,
            text_length=0,
        )

    if len(text) > settings.max_text_chars:
        text = text[: settings.max_text_chars]
        findings.append(
            ExtractionFinding(
                code="TEXT_TRUNCATED",
                severity="warning",
                message="Input text exceeded the configured processing limit and was truncated.",
            )
        )

    line_refs = _line_references(request, text)
    transactions = _extract_transaction_rows(line_refs, document_type, min_confidence) if rows_enabled else []
    fields = _extract_financial_fields(line_refs, min_confidence) if field_enabled else []

    if not transactions:
        findings.append(
            ExtractionFinding(
                code="NO_TRANSACTION_CANDIDATES",
                severity="warning",
                message="No transaction-like rows were found in the parsed text.",
            )
        )

    if not fields:
        findings.append(
            ExtractionFinding(
                code="NO_FINANCIAL_FIELDS",
                severity="warning",
                message="No document-level financial fields were found in the parsed text.",
            )
        )

    low_confidence = [
        candidate
        for candidate in [*transactions, *fields]
        if candidate.confidence < min_confidence
    ]
    if low_confidence:
        findings.append(
            ExtractionFinding(
                code="LOW_CONFIDENCE_EXTRACTION",
                severity="warning",
                message="One or more extraction candidates are below the configured confidence threshold.",
            )
        )

    status = ExtractionStatus.completed_with_warnings if findings else ExtractionStatus.completed
    return _result(
        extraction_id=extraction_id,
        request=request,
        document_type=document_type,
        status=status,
        transactions=transactions,
        fields=fields,
        findings=findings,
        min_confidence=min_confidence,
        pages_processed=_pages_processed(request, line_refs),
        text_length=len(text),
    )


def _extract_transaction_rows(
    line_refs: list[SourceReference],
    document_type: str,
    min_confidence: float,
) -> list[TransactionCandidate]:
    candidates: list[TransactionCandidate] = []
    for line in line_refs:
        amounts = _amounts(line.text)
        if not amounts:
            continue

        date_match = DATE_PATTERN.search(line.text)
        has_transaction_word = bool(
            re.search(r"\b(payment|purchase|transfer|deposit|withdrawal|credit|debit|sent|received)\b", line.text, re.IGNORECASE)
        )
        if not date_match and not has_transaction_word:
            continue

        amount = amounts[-1][1]
        currency = amounts[-1][0] or settings.default_currency
        direction = _direction(line.text, amount)
        confidence = 0.72
        reason_codes = ["AMOUNT_DETECTED"]
        if date_match:
            confidence += 0.12
            reason_codes.append("DATE_DETECTED")
        if has_transaction_word:
            confidence += 0.08
            reason_codes.append("TRANSACTION_WORD_DETECTED")
        if document_type == "unknown":
            confidence -= 0.12
            reason_codes.append("UNKNOWN_DOCUMENT_TYPE")

        candidates.append(
            TransactionCandidate(
                candidate_id=f"txn_{len(candidates) + 1:04d}",
                date_text=date_match.group(0) if date_match else None,
                description=_description_without_amounts(line.text),
                amount=abs(amount),
                currency=currency.upper(),
                direction=direction,
                source=line,
                confidence=round(max(0.0, min(confidence, 0.98)), 3),
                reason_codes=reason_codes,
            )
        )

    return candidates


def _extract_financial_fields(
    line_refs: list[SourceReference],
    min_confidence: float,
) -> list[FinancialFieldCandidate]:
    candidates: list[FinancialFieldCandidate] = []
    for line in line_refs:
        for field_name, pattern in FIELD_PATTERNS.items():
            match = pattern.search(line.text)
            if not match:
                continue

            value_text = match.group(1).strip()
            amount_match = AMOUNT_PATTERN.search(value_text)
            normalized_value = None
            currency = None
            reason_codes = ["FIELD_LABEL_DETECTED"]
            if amount_match:
                currency = _currency_code(amount_match.group(1))
                if currency == settings.default_currency and "NZ$" in line.text.upper():
                    currency = "NZD"
                normalized_value = f"{_parse_amount(amount_match.group(2)):.2f}"
                reason_codes.append("AMOUNT_DETECTED")
            elif DATE_PATTERN.search(value_text):
                normalized_value = DATE_PATTERN.search(value_text).group(0)
                reason_codes.append("DATE_DETECTED")
            else:
                normalized_value = value_text
                reason_codes.append("IDENTIFIER_DETECTED")

            candidates.append(
                FinancialFieldCandidate(
                    field_name=field_name,
                    value_text=value_text,
                    normalized_value=normalized_value,
                    currency=currency,
                    source=line,
                    confidence=0.86 if normalized_value else max(0.6, min_confidence),
                    reason_codes=reason_codes,
                )
            )

    return candidates


def _document_type(request: TransactionExtractionRequest) -> str:
    if request.document_type:
        return request.document_type.lower()
    if request.classification and request.classification.document_type:
        return request.classification.document_type.lower()
    return "unknown"


def _upstream_quality_findings(request: TransactionExtractionRequest) -> list[ExtractionFinding]:
    findings: list[ExtractionFinding] = []
    if request.quality and request.quality.low_text:
        findings.append(
            ExtractionFinding(
                code="LOW_TEXT_QUALITY_INPUT",
                severity="warning",
                message="M5 reported low extracted text quality; M7 candidates may be incomplete.",
            )
        )

    upstream_codes = {finding.code for finding in request.findings}
    if "NO_TEXT_EXTRACTED" in upstream_codes:
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_NO_TEXT_EXTRACTED",
                severity="warning",
                message="M5 reported that parsing completed without usable extracted text.",
            )
        )
    if "OCR_FALLBACK_DISABLED" in upstream_codes:
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_DISABLED",
                severity="warning",
                message="M5 reported that OCR was needed but disabled; rerun M5 with OCR enabled before expecting reliable extraction.",
            )
        )
    if upstream_codes.intersection({"TESSERACT_UNAVAILABLE", "PDF_RENDERER_UNAVAILABLE", "OCR_FAILED"}):
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_FAILURE",
                severity="warning",
                message="M5 reported an OCR runtime or processing failure; fix M5 OCR readiness before retrying extraction.",
            )
        )
    if upstream_codes.intersection({"LOW_OCR_CONFIDENCE", "OCR_TEXT_NOISY"}):
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_QUALITY_WEAK",
                severity="warning",
                message="M5 reported weak OCR text quality; M7 candidates may be incomplete or unreliable.",
            )
        )

    return findings


def _line_references(request: TransactionExtractionRequest, text: str) -> list[SourceReference]:
    if request.pages:
        page_limit = request.options.page_limit if request.options and request.options.page_limit else settings.max_page_count
        refs = []
        for page in request.pages[:page_limit]:
            for line_number, line in enumerate(page.text.splitlines(), start=1):
                if line.strip():
                    refs.append(SourceReference(page_number=page.page_number, line_number=line_number, text=line.strip()))
        return refs

    return [
        SourceReference(page_number=None, line_number=line_number, text=line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]


def _amounts(text: str) -> list[tuple[str | None, float]]:
    return [(_currency_code(match.group(1)), _parse_amount(match.group(2))) for match in AMOUNT_PATTERN.finditer(text)]


def _parse_amount(value: str) -> float:
    normalized = value.replace(" ", "")
    if "," in normalized and "." not in normalized and re.search(r",\d{2}$", normalized):
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    return float(normalized)


def _currency_code(value: str | None) -> str:
    if not value:
        return settings.default_currency
    normalized = value.upper()
    if normalized in {"$", "NZ$"}:
        return "NZD" if normalized == "NZ$" else settings.default_currency
    return normalized


def _description_without_amounts(text: str) -> str:
    return AMOUNT_PATTERN.sub("", text).strip(" -|")


def _direction(text: str, amount: float) -> str:
    lowered = text.lower()
    if amount < 0 or any(word in lowered for word in ["payment", "credit", "received", "deposit"]):
        return "credit"
    if any(word in lowered for word in ["purchase", "debit", "sent", "withdrawal", "transfer to", "transfer amount"]):
        return "debit"
    return "unknown"


def _option_min_confidence(request: TransactionExtractionRequest) -> float:
    if request.options and request.options.min_confidence is not None:
        return request.options.min_confidence
    return settings.min_transaction_confidence


def _option_bool(request: TransactionExtractionRequest, name: str, default: bool) -> bool:
    if not request.options:
        return default
    value = getattr(request.options, name)
    return default if value is None else value


def _pages_processed(request: TransactionExtractionRequest, line_refs: list[SourceReference]) -> int:
    if request.pages:
        return len({line.page_number for line in line_refs if line.page_number is not None})
    return 1 if line_refs else 0


def _result(
    extraction_id: str,
    request: TransactionExtractionRequest,
    document_type: str,
    status: ExtractionStatus,
    transactions: list[TransactionCandidate],
    fields: list[FinancialFieldCandidate],
    findings: list[ExtractionFinding],
    min_confidence: float,
    pages_processed: int,
    text_length: int,
) -> TransactionExtractionResult:
    finding_counts = dict(Counter(finding.code for finding in findings))
    debit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "debit"), 2)
    credit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "credit"), 2)
    amount_total = round(sum(candidate.amount for candidate in transactions), 2)
    low_confidence_count = sum(
        1
        for candidate in [*transactions, *fields]
        if candidate.confidence < min_confidence
    )

    summary = ExtractionSummary(
        transaction_candidate_count=len(transactions),
        financial_field_candidate_count=len(fields),
        debit_total=debit_total,
        credit_total=credit_total,
        amount_total=amount_total,
        pages_processed=pages_processed,
        text_length=text_length,
        low_confidence_candidate_count=low_confidence_count,
    )
    evaluation = ExtractionEvaluation(
        extraction_id=extraction_id,
        parse_id=request.parse_id,
        document_type=document_type,
        status=status,
        transaction_candidate_count=len(transactions),
        financial_field_candidate_count=len(fields),
        finding_counts=finding_counts,
        min_confidence=min_confidence,
        text_length=text_length,
        pages_processed=pages_processed,
    )

    return TransactionExtractionResult(
        extraction_id=extraction_id,
        status=status,
        parse_id=request.parse_id,
        document=request.document,
        document_type=document_type,
        transaction_candidates=transactions,
        financial_field_candidates=fields,
        summary=summary,
        evaluation=evaluation,
        findings=findings,
    )
