"""M7 - Transaction Extraction Module Start
Extracts transaction and financial field candidates from parsed document text.
M7 End"""

import re
import uuid
from collections import Counter

from app.config import settings
from app.models.extraction import (
    EntityCandidate,
    ExtractionEvaluation,
    ExtractedTable,
    ExtractedTableRow,
    ExtractionFinding,
    ExtractionSummary,
    ExtractionStatus,
    FinancialFieldCandidate,
    InstallmentCandidate,
    LineItemCandidate,
    QualityMetadata,
    ReconciliationResult,
    ReferenceCandidate,
    SectionCandidate,
    SourceReference,
    TransactionCandidate,
    TransactionExtractionRequest,
    TransactionExtractionResult,
)
from app.services.transaction_classification_service import classify_transaction_candidate


AMOUNT_PATTERN = re.compile(
    r"(?<![\d.])(?:(PHP|USD|AUD|NZD|NZ\$|\$)\s*)?([+-]?\d{1,3}(?:,\d{3})*(?:\.\s?\d{2,3}|,\d{2})|[+-]?\d+(?:\.\s?\d{2,3}|,\d{2}))(?!\d|\.\d)",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[-\s](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*[-\s]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
SHORT_NUMERIC_DATE_PATTERN = re.compile(r"\b(?P<day>\d{1,2})[/-](?P<month>\d{1,2})(?![/-]\d)\b")
MONTH_YEAR_PATTERN = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?P<year>\d{2,4})\b",
    re.IGNORECASE,
)
MONTH_DAY_PATTERN = re.compile(
    r"^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}$",
    re.IGNORECASE,
)
MONTH_DAY_FRAGMENT = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}"
DAY_MONTH_FRAGMENT = r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
DAY_MONTH_TOKEN_PATTERN = re.compile(rf"^{DAY_MONTH_FRAGMENT}$", re.IGNORECASE)
DAY_MONTH_PARTS_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?$",
    re.IGNORECASE,
)
COMPACT_DAY_MONTH_TOKEN_PATTERN = re.compile(
    r"^(?P<day>\d{1,2})(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?$",
    re.IGNORECASE,
)
DAY_MONTH_YEAR_PATTERN = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(?P<year>\d{2,4})\b",
    re.IGNORECASE,
)
MONTH_NUMBERS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
COMPACT_DAY_MONTH_YEAR_PATTERN = re.compile(
    r"\b(?P<day>\d{1,2})(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?(?P<year>\d{2,4})\b",
    re.IGNORECASE,
)
LAYOUT_AMOUNT_PATTERN = re.compile(r"^(?P<amount>[+-]?\d{1,3}(?:,\d{3})*(?:\.\d{2}|,\d{2})|[+-]?\d+(?:\.\d{2}|,\d{2}))(?P<credit>CR)?$", re.IGNORECASE)
FOREIGN_CURRENCY_AMOUNT_PATTERN = re.compile(
    r"\b(?:USD|AUD|NZD|EUR|GBP|JPY|KRW|SGD|HKD|CAD|CHF|CNY|THB|MYR|IDR|TWD)\b\s+[+-]?\d{1,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2})?",
    re.IGNORECASE,
)
STATEMENT_SUMMARY_PATTERNS = {
    "previous_statement_balance": re.compile(r"\bprevious\s+statement\s+balance\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "payments_and_credits": re.compile(r"\bpayments?\s*&\s*credits\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "purchases_and_debits": re.compile(r"\bpurchases?\s*&\s*debits\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "total_account_balance": re.compile(r"\btotal\s+account\s+balance\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "total_due": re.compile(r"\btotal\s+due\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "minimum_payment": re.compile(r"\bminimum\s+payment\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "payment_due_date": re.compile(r"\bpayment\s+due\s+date\s+([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b", re.IGNORECASE),
    "credit_limit": re.compile(r"\bcredit\s+limit\s*(?:\(PHP\))?\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
    "available_credit": re.compile(r"\bavailable\s+credit\s*(?:\(PHP\))?\s+([0-9,]+\.\d{2})(CR)?\b", re.IGNORECASE),
}
SIDE_SUMMARY_PATTERN = re.compile(
    r"\b(previous statement balance|payments?\s*&\s*credits|purchases?\s*&\s*debits|outstanding installments|total account balance|payment summary|payment due date|minimum payment|credit limit|cash limit|available credit|monthly interest rate|purchase\s+\d|cash advance\s+\d|we'?re encouraging|you'?ll be able)\b",
    re.IGNORECASE,
)
COMBINED_STATEMENT_ROW_PATTERN = re.compile(
    rf"^(?P<date_text>{MONTH_DAY_FRAGMENT})\s+(?P<posted_date_text>{MONTH_DAY_FRAGMENT})\s+(?P<description>.+?)\s+(?P<amount>[+-]?\d{{1,3}}(?:,\d{{3}})*(?:\.\s?\d{{2}}|,\d{{2}})|[+-]?\d+(?:\.\s?\d{{2}}|,\d{{2}}))$",
    re.IGNORECASE,
)
COMBINED_STATEMENT_ROW_WITHOUT_AMOUNT_PATTERN = re.compile(
    rf"^(?P<date_text>{MONTH_DAY_FRAGMENT})\s+(?P<posted_date_text>{MONTH_DAY_FRAGMENT})\s+(?P<description>.+?)$",
    re.IGNORECASE,
)
OCR_STATEMENT_DATE_PAIR_PATTERN = re.compile(
    rf"\b(?P<date_text>{DAY_MONTH_FRAGMENT})\s+(?P<posted_date_text>{DAY_MONTH_FRAGMENT})\b",
    re.IGNORECASE,
)
TABLE_HEADER_TERMS = {"transaction", "date", "post date", "posting date", "description", "details", "amount", "debit", "credit"}
TABLE_STOP_PATTERN = re.compile(
    r"\b(balance summary|rewards?|points?|important advisory|payment instruction|your installment plan|date expiry|total due|total amount due)\b",
    re.IGNORECASE,
)
TABLE_HARD_STOP_PATTERN = re.compile(
    r"\b(balance summary|important advisory|payment instruction|your installment plan|date expiry|total due|total amount due|please detach)\b",
    re.IGNORECASE,
)
TABLE_SKIP_PATTERN = re.compile(
    r"\b(statement of account|customer number|card type)\b|^\d{4,}[-\d ]+",
    re.IGNORECASE,
)
FIELD_PATTERNS = {
    "total_amount_due": (r"TOTAL AMOUNT DUE", re.compile(r"\btotal\s+amount\s+due\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "minimum_amount_due": (r"MINIMUM AMOUNT DUE", re.compile(r"\bminimum\s+amount\s+due\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "payment_due_date": (r"PAYMENT DUE DATE", re.compile(r"\bpayment\s+due\s+date\s+(.+)$", re.IGNORECASE)),
    "statement_date": (r"STATEMENT DATE", re.compile(r"\bstatement\s+date\s+(.+)$", re.IGNORECASE)),
    "credit_limit": (r"CREDIT LIMIT", re.compile(r"\bcredit\s+limit\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "previous_balance": (r"PREVIOUS BALANCE", re.compile(r"\bprevious\s+balance\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "past_due_amount": (r"PAST DUE AMOUNT", re.compile(r"\bpast\s+due\s+amount\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "outstanding_balance": (r"OUTSTANDING BALANCE", re.compile(r"\b(?:total\s+)?outstanding\s+balance\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "transfer_amount": (r"TRANSFER AMOUNT", re.compile(r"\btransfer\s+amount\s+(?:PHP\s*)?([0-9,]+\.\d{2})", re.IGNORECASE)),
    "confirmation_number": (r"CONFIRMATION NO.", re.compile(r"\bconfirmation\s+no\.?\s+([A-Z0-9-]+)", re.IGNORECASE)),
    "reference_number": (r"REFERENCE NO.", re.compile(r"\bre(?:f|ference)\.?\s+no\.?\s+([A-Z0-9-]+)", re.IGNORECASE)),
    "invoice_number": (r"INVOICE NO.", re.compile(r"\b(?:tax\s+)?invoice\s+no\.?:?\s+([A-Z0-9-]+)", re.IGNORECASE)),
    "receipt_total": (r"TOTAL", re.compile(r"\b(?:tax\s+invoice:\s*)?total(?:\s+due)?(?:\s*\([^)]*\))?\s*[:;-]?\s*(?!GST\b)(?:NZD|NZ\$|\$|PHP\s*)?([0-9,]+(?:\.\s?\d{2,3}|,\d{2}))(?!\d|\.\d)", re.IGNORECASE)),
    "total_gst": (r"TOTAL GST", re.compile(r"\btotal\s+GST\s+\$?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE)),
    "gst_amount": (r"INCLUDES GST", re.compile(r"\bincludes\s+GST\s+of\s+\$?([0-9,]+(?:\.\s?\d{2}|,\d{2}))", re.IGNORECASE)),
    "purchase_amount": (r"PURCHASE", re.compile(r"\bpurchase\s+(?:NZD|NZ\$|\$|PHP\s*)?([0-9,]+(?:\.\s?\d{2,3}|,\d{2}))(?!\d|\.\d)", re.IGNORECASE)),
    "card_receipt_amount": (r"NZ$", re.compile(r"\b(?:NZD|NZ\$)\s*([0-9,]+(?:\.\s?\d{2,3}|,\d{2}))(?!\d|\.\d)", re.IGNORECASE)),
}
REFERENCE_FIELD_NAMES = {"confirmation_number", "reference_number", "invoice_number"}
RECEIPT_TOTAL_AMOUNT_PATTERN = re.compile(
    r"\b(?:sub\s*total|subtotal|subfotal|total(?:\s+due)?|amount\s+due|due\s+amount|sale)\b.{0,24}?(?:NZD|NZ\$|\$|PHP|B)?\s*([0-9]{1,3}(?:,\d{3})*(?:\.\s?\d{2,3}|,\d{2})|[0-9]+(?:\.\s?\d{2,3}|,\d{2}))(?!\d|\.\d)",
    re.IGNORECASE,
)
RECEIPT_TAX_ONLY_CONTEXT = re.compile(r"\b(?:gst|tax|change|rounding)\b", re.IGNORECASE)
MALFORMED_AMOUNT_TOKEN_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{3})+\.\d{2}\b")
STATEMENT_SHAPE_FIELD_NAMES = {
    "statement_date",
    "payment_due_date",
    "credit_limit",
    "previous_balance",
    "previous_statement_balance",
    "payments_and_credits",
    "purchases_and_debits",
    "total_account_balance",
    "total_amount_due",
    "minimum_amount_due",
    "minimum_payment",
    "outstanding_balance",
}
STATEMENT_EXCLUSIVE_FIELD_NAMES = {
    "statement_date",
    "credit_limit",
    "previous_balance",
    "previous_statement_balance",
    "payments_and_credits",
    "purchases_and_debits",
    "total_account_balance",
}


def extract_transactions(request: TransactionExtractionRequest) -> TransactionExtractionResult:
    extraction_id = f"extract_{uuid.uuid4().hex[:16]}"
    findings: list[ExtractionFinding] = []
    document_type = _document_type(request)
    min_confidence = _option_min_confidence(request)
    field_enabled = _option_bool(request, "enable_field_extraction", settings.enable_field_extraction)
    rows_enabled = _option_bool(request, "enable_transaction_rows", settings.enable_transaction_rows)
    line_items_enabled = _option_bool(request, "enable_line_items", settings.enable_line_items)

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
            sections=[],
            entities=[],
            references=[],
            line_items=[],
            installments=[],
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
    sections = _extract_sections(line_refs)
    malformed_amount_findings = _malformed_amount_findings(line_refs)
    receipt_like_unknown = document_type == "unknown" and _looks_like_receipt_ocr(line_refs)
    layout_transactions = _extract_layout_statement_rows(request, document_type) if rows_enabled else []
    transactions = layout_transactions or (
        _extract_transaction_rows(line_refs, document_type, min_confidence, findings) if rows_enabled else []
    )
    fields = _extract_financial_fields(line_refs, min_confidence) if field_enabled else []
    statement_shape_detected = _has_statement_shape_evidence(line_refs, fields, sections)
    if rows_enabled and (not transactions or receipt_like_unknown or document_type in {"receipt", "invoice"}):
        if statement_shape_detected:
            findings.append(
                ExtractionFinding(
                    code="STATEMENT_SHAPE_RECEIPT_FALLBACK_SUPPRESSED",
                    severity="warning",
                    message="Statement-like fields or sections were present, so receipt-style total fallback was suppressed.",
                )
            )
        else:
            derived_transactions = _derive_receipt_invoice_transactions(fields, line_refs, document_type)
            if derived_transactions:
                transactions = derived_transactions
    installment_candidates: list[InstallmentCandidate] = []
    if _canonical_document_type(document_type) in {"statement", "unknown"}:
        payment_fields, installment_candidates, transactions = _separate_statement_payment_and_installments(
            transactions,
            line_refs,
        )
        fields.extend(payment_fields)
        fields.extend(_flattened_statement_payment_fields(line_refs, fields))
        repaired_transactions = _repair_statement_purchase_gap_transactions(
            request=request,
            transactions=transactions,
            fields=fields,
            document_type=document_type,
            line_refs=line_refs,
        )
        if repaired_transactions:
            transactions = repaired_transactions
            findings.append(
                ExtractionFinding(
                    code="OCR_DAMAGED_TRANSACTION_ROW_REPAIRED",
                    severity="warning",
                    message=(
                        "One or more statement transaction rows were repaired from OCR layout and statement "
                        "purchases/debits reconciliation evidence."
                    ),
                )
            )
    entities = _extract_entities(line_refs, document_type)
    references = _extract_references(fields, line_refs)
    line_items = _extract_line_items(line_refs) if line_items_enabled else []
    if settings.enable_transaction_classification:
        document_subtype = request.classification.document_subtype if request.classification else "unknown"
        transactions = [
            classify_transaction_candidate(
                candidate,
                document_type=document_type,
                document_subtype=document_subtype,
            )
            for candidate in transactions
        ]
        if any(
            "RECOGNITION_SETTINGS_UNAVAILABLE" in candidate.transaction_type_reason_codes
            or "RECOGNITION_SETTINGS_UNAVAILABLE" in candidate.spending_category_reason_codes
            for candidate in transactions
        ):
            findings.append(
                ExtractionFinding(
                    code="RECOGNITION_SETTINGS_UNAVAILABLE",
                    severity="warning",
                    message="Recognition settings could not be loaded from Stats Data, so transaction and spending classifications need review.",
                )
            )

    if malformed_amount_findings and not transactions:
        findings.extend(malformed_amount_findings)

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
        for candidate in [*transactions, *fields, *installment_candidates]
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

    findings.extend(_reconciliation_review_findings(transactions, fields))

    status = ExtractionStatus.completed_with_warnings if findings else ExtractionStatus.completed
    return _result(
        extraction_id=extraction_id,
        request=request,
        document_type=document_type,
        status=status,
        transactions=transactions,
        fields=fields,
        sections=sections,
        entities=entities,
        references=references,
        line_items=line_items,
        installments=installment_candidates,
        findings=findings,
        min_confidence=min_confidence,
        pages_processed=_pages_processed(request, line_refs),
        text_length=len(text),
    )


def _extract_transaction_rows(
    line_refs: list[SourceReference],
    document_type: str,
    min_confidence: float,
    findings: list[ExtractionFinding],
) -> list[TransactionCandidate]:
    reconstructed = _extract_statement_table_rows(line_refs, document_type)
    if reconstructed:
        return reconstructed
    flattened_statement_rows = _extract_flattened_statement_rows(line_refs, document_type)
    if flattened_statement_rows:
        return flattened_statement_rows

    candidates: list[TransactionCandidate] = []
    statement_year = _statement_year(line_refs)
    for line in line_refs:
        combined = _combined_statement_row_candidate(
            line=line,
            text=line.text.strip(),
            statement_year=statement_year,
            document_type=document_type,
            candidate_number=len(candidates) + 1,
        )
        if combined:
            candidates.append(combined)
            continue

        amounts = _amounts(line.text)
        if not amounts:
            continue

        date_match = DATE_PATTERN.search(line.text)
        has_transaction_word = bool(
            re.search(r"\b(payment|purchase|transfer|deposit|withdrawal|credit|debit|sent|received)\b", line.text, re.IGNORECASE)
        )
        if not date_match and not has_transaction_word:
            continue
        if _looks_like_non_transaction_financial_block(line.text, amounts):
            findings.append(
                ExtractionFinding(
                    code="NON_TRANSACTION_FINANCIAL_BLOCK",
                    severity="info",
                    message="A financial-looking block was kept out of transaction candidates because it looks like a summary, header, or advisory block.",
                )
            )
            continue

        amount = amounts[-1][1]
        currency = amounts[-1][0] or settings.default_currency
        if currency == settings.default_currency:
            currency = _infer_currency_from_text(line.text)
        description = _description_without_amounts(line.text)
        if document_type in {"receipt", "invoice"}:
            description = _receipt_invoice_description(line, document_type)
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
                description=description,
                amount=abs(amount),
                currency=currency.upper(),
                direction=direction,
                source=line,
                confidence=round(max(0.0, min(confidence, 0.98)), 3),
                reason_codes=reason_codes,
            )
        )

    return candidates


def _extract_layout_statement_rows(
    request: TransactionExtractionRequest,
    document_type: str,
) -> list[TransactionCandidate]:
    rows = _layout_rows(request)
    if not rows:
        return []

    statement_year = _statement_year(_line_references(request, request.text or ""))
    legacy_candidates = _extract_layout_statement_rows_from_rows(
        rows=rows,
        document_type=document_type,
        statement_year=statement_year,
    )
    region_rows = _layout_statement_region_rows(rows)
    if region_rows:
        region_candidates = _extract_layout_statement_rows_from_rows(
            rows=region_rows,
            document_type=document_type,
            statement_year=statement_year,
        )
        if _prefer_layout_region_candidates(region_candidates, legacy_candidates):
            legacy_candidates = region_candidates

    grid_source_rows = region_rows or rows
    grid_candidates = _extract_ocr_statement_grid_rows(
        rows=grid_source_rows,
        document_type=document_type,
        statement_year=statement_year,
    )
    if _prefer_ocr_statement_grid_candidates(grid_candidates, legacy_candidates):
        return grid_candidates

    return legacy_candidates


def _prefer_layout_region_candidates(
    region_candidates: list[TransactionCandidate],
    legacy_candidates: list[TransactionCandidate],
) -> bool:
    if not region_candidates:
        return False
    if not legacy_candidates:
        return True
    if len(region_candidates) >= len(legacy_candidates):
        return True

    legacy_count = len(legacy_candidates)
    region_count = len(region_candidates)
    legacy_total = round(sum(candidate.amount for candidate in legacy_candidates), 2)
    region_total = round(sum(candidate.amount for candidate in region_candidates), 2)
    if legacy_count >= 4 and region_count < max(2, int(legacy_count * 0.6)):
        return False
    if legacy_total > 0 and region_total > legacy_total * 1.5:
        return False
    return region_count >= legacy_count - 1


def _prefer_ocr_statement_grid_candidates(
    grid_candidates: list[TransactionCandidate],
    fallback_candidates: list[TransactionCandidate],
) -> bool:
    if len(grid_candidates) < 3:
        return False
    if not fallback_candidates:
        return True
    if len(grid_candidates) <= len(fallback_candidates):
        return False
    fallback_total = round(sum(candidate.amount for candidate in fallback_candidates), 2)
    grid_total = round(sum(candidate.amount for candidate in grid_candidates), 2)
    if fallback_total > 0 and grid_total > fallback_total * 3:
        return False
    return True


def _extract_layout_statement_rows_from_rows(
    rows: list[dict[str, object]],
    document_type: str,
    statement_year: int | None,
) -> list[TransactionCandidate]:
    candidates: list[TransactionCandidate] = []
    active: dict[str, object] | None = None
    previous_page: int | None = None
    in_transaction_table = False
    pending_prefix: list[str] = []
    side_exclusion_pending = False

    for row in rows:
        text = row["text"]
        page_number = int(row["page_number"])
        lowered = text.lower()
        if "description" in lowered and "amount" in lowered and ("tran" in lowered or "date" in lowered):
            in_transaction_table = True
            continue
        if not in_transaction_table:
            continue
        if previous_page is not None and page_number != previous_page and active:
            _append_layout_candidate(candidates, active, statement_year, document_type)
            active = None
            pending_prefix = []
            side_exclusion_pending = False
        previous_page = page_number

        if _is_table_stop(text) or "continued on next page" in text.lower():
            if active:
                _append_layout_candidate(candidates, active, statement_year, document_type)
                active = None
            pending_prefix = []
            side_exclusion_pending = False
            if _is_table_hard_stop(text):
                in_transaction_table = False
            continue

        date_pair = _layout_date_pair(row["tokens"])
        amount_token = _layout_amount_token_after_dates(row["tokens"], row.get("token_confidences")) if date_pair else None
        text_row_parts = _layout_row_parts_from_text(text) if date_pair else None
        if date_pair and active:
            _append_layout_candidate(candidates, active, statement_year, document_type)
            active = None
        if date_pair and (amount_token or text_row_parts):
            amount_confidence = amount_token[3] if amount_token else None
            if text_row_parts:
                description, amount_value, text_reason_codes = text_row_parts
            else:
                amount_text, amount_value, amount_index, amount_confidence = amount_token
                description = _layout_description(row["tokens"], date_pair, amount_text, amount_index)
                text_reason_codes = []
            if pending_prefix:
                if _layout_noisy_description(description):
                    description = _clean_reconstructed_description(" ".join(pending_prefix))
                else:
                    description = _clean_reconstructed_description(" ".join([*pending_prefix, description]))
                text_reason_codes.append("DESCRIPTION_PREFIX_REPAIRED")
            if side_exclusion_pending:
                text_reason_codes.append("SIDE_COLUMN_TEXT_EXCLUDED")
            text_reason_codes.extend(_layout_region_reason_codes(row))
            active = {
                "page_number": page_number,
                "line_number": int(row["line_number"]),
                "date_text": date_pair[0],
                "posted_date_text": date_pair[1],
                "description_parts": [description],
                "amount": amount_value,
                "source_text": text,
                "confidence": row["confidence"],
                "amount_confidence": amount_confidence,
                "reason_codes": text_reason_codes,
            }
            pending_prefix = []
            side_exclusion_pending = False
            continue

        if date_pair:
            description = _layout_description(row["tokens"], date_pair, "", None)
            if pending_prefix:
                if _layout_noisy_description(description):
                    description = _clean_reconstructed_description(" ".join(pending_prefix))
                else:
                    description = _clean_reconstructed_description(" ".join([*pending_prefix, description]))
            active = {
                "page_number": page_number,
                "line_number": int(row["line_number"]),
                "date_text": date_pair[0],
                "posted_date_text": date_pair[1],
                "description_parts": [description],
                "amount": None,
                "source_text": text,
                "confidence": row["confidence"],
                "reason_codes": ["DESCRIPTION_PREFIX_REPAIRED"] if pending_prefix else [],
            }
            active["reason_codes"].extend(_layout_region_reason_codes(row))
            if side_exclusion_pending:
                active["reason_codes"].append("SIDE_COLUMN_TEXT_EXCLUDED")
            pending_prefix = []
            side_exclusion_pending = False
            continue

        if active and _layout_side_column_text(text):
            active.setdefault("reason_codes", []).append("SIDE_COLUMN_TEXT_EXCLUDED")
            continue

        follow_up_amount = _last_layout_amount_token(row["tokens"], row.get("token_confidences"))
        if active and follow_up_amount:
            if row.get("region_detected") and not re.search(r"[A-Za-z]{3,}", text):
                active.setdefault("reason_codes", []).append("SIDE_COLUMN_TEXT_EXCLUDED")
                continue
            amount_text, amount_value, amount_confidence = follow_up_amount
            active["amount"] = amount_value
            active["amount_confidence"] = amount_confidence
            active["source_text"] = f"{active['source_text']} {text}"
            active["confidence"] = _mean_confidence([active.get("confidence"), row["confidence"]])
            active.setdefault("reason_codes", []).extend(_layout_region_reason_codes(row))
            continue

        if active and active.get("amount") is not None and _layout_prefix_text(text) and not _layout_suffix_fragment(text):
            _append_layout_candidate(candidates, active, statement_year, document_type)
            active = None
            pending_prefix = _remember_layout_prefix(pending_prefix, text)
            continue

        if active and _layout_continuation_text(text):
            active["description_parts"].append(_strip_side_summary_text(text))
            active["source_text"] = f"{active['source_text']} {text}"
            active["confidence"] = _mean_confidence([active.get("confidence"), row["confidence"]])
            active.setdefault("reason_codes", []).append("DESCRIPTION_SUFFIX_REPAIRED")
            active.setdefault("reason_codes", []).extend(_layout_region_reason_codes(row))
            continue

        if _layout_prefix_text(text):
            if active:
                _append_layout_candidate(candidates, active, statement_year, document_type)
                active = None
            pending_prefix = _remember_layout_prefix(pending_prefix, text)
            continue

        if _layout_side_column_text(text):
            side_exclusion_pending = True
            continue

        if active:
            _append_layout_candidate(candidates, active, statement_year, document_type)
            active = None
        pending_prefix = []
        side_exclusion_pending = False

    if active:
        _append_layout_candidate(candidates, active, statement_year, document_type)

    return candidates


def _extract_ocr_statement_grid_rows(
    rows: list[dict[str, object]],
    document_type: str,
    statement_year: int | None,
) -> list[TransactionCandidate]:
    candidates: list[TransactionCandidate] = []
    header_seen_by_page: set[int] = set()
    candidate_rows: list[dict[str, object]] = []
    grid_table_active = False

    for row in rows:
        page_number = int(row["page_number"])
        text = str(row["text"])
        if _layout_grid_header_row(row):
            header_seen_by_page.add(page_number)
            grid_table_active = True
            continue
        if _is_table_hard_stop(text):
            header_seen_by_page.discard(page_number)
            grid_table_active = False
            continue
        parsed = _layout_grid_candidate(row)
        if not parsed:
            continue
        parsed["after_header"] = page_number in header_seen_by_page or grid_table_active
        candidate_rows.append(parsed)

    if not candidate_rows:
        return []

    anchored_rows = [row for row in candidate_rows if row.get("after_header")]
    rows_to_emit = anchored_rows if len(anchored_rows) >= 2 else candidate_rows
    if len(rows_to_emit) < 3:
        return []

    for parsed in rows_to_emit:
        active = {
            "page_number": parsed["page_number"],
            "line_number": parsed["line_number"],
            "date_text": parsed["date_text"],
            "posted_date_text": parsed["posted_date_text"],
            "description_parts": [parsed["description"]],
            "amount": parsed["amount"],
            "source_text": parsed["source_text"],
            "confidence": parsed["confidence"],
            "amount_confidence": parsed["amount_confidence"],
            "reason_codes": [
                "OCR_TABLE_GRID_ROW_RECONSTRUCTED",
                "OCR_TABLE_GRID_POSITIONAL_DATES",
                "OCR_TABLE_GRID_POSITIONAL_AMOUNT",
            ],
        }
        _append_layout_candidate(candidates, active, statement_year, document_type)

    return candidates


def _layout_grid_header_row(row: dict[str, object]) -> bool:
    if _layout_table_header_row(row):
        return True
    blocks = _layout_row_blocks(row)
    left_tokens = {
        token
        for block in blocks
        if block.x < 360
        for token in re.findall(r"[a-z]+", block.text.lower())
    }
    return bool(left_tokens & {"post", "posting"}) and bool(left_tokens & {"tran", "transaction", "transactions"})


def _layout_grid_candidate(row: dict[str, object]) -> dict[str, object] | None:
    blocks = sorted(_layout_row_blocks(row), key=lambda block: block.x)
    if len(blocks) < 5:
        return None

    date_pair = _layout_grid_date_pair(blocks)
    if not date_pair:
        return None
    date_text, posted_date_text, _, posted_end_index, posted_x_end = date_pair

    amount_match = _layout_grid_amount(blocks, posted_end_index + 1, posted_x_end)
    if not amount_match:
        return None
    amount_index, amount_text, amount_value, amount_confidence = amount_match

    description_blocks = [
        block
        for block in blocks[posted_end_index + 1 : amount_index]
        if _layout_grid_description_token(block.text, block.x)
    ]
    description = _clean_reconstructed_description(" ".join(block.text.strip() for block in description_blocks))
    if not description or _is_summary_description(description):
        return None

    source_blocks = [*blocks[: posted_end_index + 1], *description_blocks, blocks[amount_index]]
    if amount_index + 1 < len(blocks) and blocks[amount_index + 1].text.strip().upper() == "CR":
        source_blocks.append(blocks[amount_index + 1])
    source_text = _normalize_extracted_line(" ".join(block.text.strip() for block in source_blocks if block.text.strip()))

    return {
        "page_number": int(row["page_number"]),
        "line_number": int(row["line_number"]),
        "date_text": date_text,
        "posted_date_text": posted_date_text,
        "description": description,
        "amount": amount_value,
        "source_text": source_text,
        "confidence": row["confidence"],
        "amount_confidence": amount_confidence,
        "amount_text": amount_text,
    }


def _layout_grid_date_pair(blocks: list[object]) -> tuple[str, str, int, int, float] | None:
    dates: list[tuple[str, int, int, float, float]] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        token = block.text.strip()
        compact = COMPACT_DAY_MONTH_TOKEN_PATTERN.match(token)
        if compact and block.x < 330 and _valid_day_month_parts(compact.group("day"), compact.group("month")):
            date_text = f"{compact.group('day')} {compact.group('month')}"
            dates.append((date_text, index, index, block.x, block.x + block.width))
            index += 1
            continue
        if re.fullmatch(r"\d{1,2}", token) and index + 1 < len(blocks):
            month_block = blocks[index + 1]
            month_token = month_block.text.strip()
            if (
                _layout_month_token(month_token)
                and _valid_day_month_parts(token, month_token)
                and block.x < 330
                and month_block.x - block.x < 80
            ):
                dates.append((f"{token} {month_token}", index, index + 1, block.x, month_block.x + month_block.width))
                index += 2
                continue
        index += 1

    if len(dates) < 2:
        return None
    first, second = dates[0], dates[1]
    if second[3] <= first[3] + 20:
        return None
    return first[0], second[0], first[2], second[2], second[4]


def _layout_month_token(token: str) -> bool:
    return token[:3].lower().strip(".") in MONTH_NUMBERS


def _valid_day_month_parts(day: str, month: str) -> bool:
    try:
        day_value = int(day)
    except ValueError:
        return False
    return 1 <= day_value <= 31 and month[:3].lower().strip(".") in MONTH_NUMBERS


def _valid_day_month_text(text: str) -> bool:
    match = DAY_MONTH_PARTS_PATTERN.match(text.strip())
    return bool(match and _valid_day_month_parts(match.group("day"), match.group("month")))


def _layout_grid_amount(
    blocks: list[object],
    start_index: int,
    posted_x_end: float,
) -> tuple[int, str, float, float | None] | None:
    has_description = False
    side_start_x = _layout_side_region_start_x(blocks)
    amount_candidates: list[tuple[int, str, float, float | None, float]] = []
    for index in range(start_index, len(blocks)):
        block = blocks[index]
        token = block.text.strip()
        if block.x <= posted_x_end:
            continue
        if _layout_grid_description_token(token, block.x):
            has_description = True
        normalized = token.replace(" ", "")
        match = LAYOUT_AMOUNT_PATTERN.match(normalized)
        if not match or not has_description:
            continue
        amount = _try_parse_amount(match.group("amount"))
        if amount is None:
            continue
        next_token = blocks[index + 1].text.strip().upper() if index + 1 < len(blocks) else ""
        if match.group("credit") or next_token == "CR":
            amount = -abs(amount)
        if side_start_x is not None and block.x >= side_start_x:
            continue
        amount_candidates.append((index, token, amount, _token_confidence([block.confidence], 0), block.x))
    if not amount_candidates:
        return None

    hsbc_band_candidates = [candidate for candidate in amount_candidates if 600 <= candidate[4] <= 760]
    selected = hsbc_band_candidates[-1] if hsbc_band_candidates else amount_candidates[-1]
    return selected[0], selected[1], selected[2], selected[3]


def _layout_grid_description_token(token: str, x: float) -> bool:
    cleaned = token.strip().strip("._")
    if len(cleaned) < 2:
        return False
    if LAYOUT_AMOUNT_PATTERN.match(cleaned.replace(" ", "")):
        return False
    if _layout_region_side_token(cleaned) and x > 480:
        return False
    return bool(re.search(r"[A-Za-z]", cleaned))


def _layout_rows(request: TransactionExtractionRequest) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    line_number = 0
    for page in request.pages:
        blocks = [block for block in page.ocr_word_blocks if block.text.strip()]
        if not blocks:
            continue
        sorted_blocks = sorted(blocks, key=lambda block: (block.y + block.height / 2, block.x))
        heights = sorted(block.height for block in sorted_blocks if block.height > 0)
        median_height = heights[len(heights) // 2] if heights else 12
        tolerance = max(12, median_height * 0.9)
        grouped: list[list[object]] = []
        centers: list[float] = []
        for block in sorted_blocks:
            center = block.y + block.height / 2
            target_index = next((index for index, row_center in enumerate(centers) if abs(row_center - center) <= tolerance), None)
            if target_index is None:
                grouped.append([block])
                centers.append(center)
                continue
            grouped[target_index].append(block)
            centers[target_index] = (centers[target_index] + center) / 2

        for group in grouped:
            ordered = sorted(group, key=lambda block: block.x)
            tokens = [block.text.strip() for block in ordered if block.text.strip()]
            token_confidences = [block.confidence for block in ordered if block.text.strip()]
            text = " ".join(tokens)
            if not text or _layout_noise_row(text):
                continue
            line_number += 1
            confidence_values = [block.confidence for block in ordered if block.confidence is not None]
            text_blocks = [block for block in ordered if block.text.strip()]
            rows.append(
                {
                    "page_number": page.page_number,
                    "line_number": line_number,
                    "tokens": tokens,
                    "token_confidences": token_confidences,
                    "text": _normalize_extracted_line(text),
                    "confidence": round(sum(confidence_values) / len(confidence_values) / 100, 3) if confidence_values else 0.78,
                    "blocks": text_blocks,
                    "x_min": min((block.x for block in text_blocks), default=0),
                    "x_max": max((block.x + block.width for block in text_blocks), default=0),
                    "y_center": sum((block.y + block.height / 2 for block in text_blocks), 0.0) / len(text_blocks) if text_blocks else 0,
                }
            )
    return rows


def _layout_statement_region_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    rows_by_page: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        rows_by_page.setdefault(int(row["page_number"]), []).append(row)

    page_anchors: dict[int, tuple[int, dict[str, float]]] = {}
    for page_num, page_rows in rows_by_page.items():
        header_index = next((index for index, row in enumerate(page_rows) if _layout_table_header_row(row)), None)
        if header_index is None:
            continue
        anchors = _layout_table_anchors(page_rows[header_index])
        if anchors:
            page_anchors[page_num] = (header_index, anchors)

    if not page_anchors:
        return []

    any_interference = any(
        _layout_region_interference_detected(rows_by_page[pn][hi + 1 :])
        for pn, (hi, _) in page_anchors.items()
    )
    if not any_interference:
        return []

    region_rows: list[dict[str, object]] = []
    active_anchors: dict[str, float] | None = None
    for page_num in sorted(rows_by_page):
        page_rows = rows_by_page[page_num]
        if page_num in page_anchors:
            header_index, anchors = page_anchors[page_num]
            active_anchors = anchors
            start = header_index
        else:
            anchors = active_anchors
            if anchors is None:
                continue
            start = 0
        for row in page_rows[start:]:
            clipped = _layout_region_clipped_row(row, anchors)
            if clipped:
                region_rows.append(clipped)
            if _is_table_hard_stop(str(row["text"])):
                break

    return region_rows


def _layout_region_interference_detected(rows: list[dict[str, object]]) -> bool:
    for row in rows:
        text = str(row["text"])
        if re.search(r"\bplease\s+detach\b|\bpayment\s+slip\b", text, re.IGNORECASE):
            return True
        side_start_x = _layout_side_region_start_x(_layout_row_blocks(row))
        amount_x = _layout_transaction_amount_x(row)
        if side_start_x is not None and amount_x is not None and side_start_x + 28 < amount_x:
            return True
    return False


def _layout_table_header_row(row: dict[str, object]) -> bool:
    text = str(row["text"]).lower()
    return "description" in text and "amount" in text and ("tran" in text or "post" in text or "date" in text)


def _layout_table_anchors(row: dict[str, object]) -> dict[str, float] | None:
    blocks = _layout_row_blocks(row)
    if not blocks:
        return None
    description_blocks = [block for block in blocks if "description" in block.text.lower() or "details" in block.text.lower()]
    amount_blocks = [
        block
        for block in blocks
        if any(term in block.text.lower() for term in ["amount", "debit", "credit"])
        and (not description_blocks or block.x > min(desc.x for desc in description_blocks))
    ]
    if not description_blocks or not amount_blocks:
        return None
    description_x = min(block.x for block in description_blocks)
    amount_x = min(block.x for block in amount_blocks)
    if amount_x <= description_x:
        return None
    return {
        "table_x_min": max(0.0, min(block.x for block in blocks) - 24),
        "description_x": description_x,
        "amount_x": amount_x,
        "amount_left": max(description_x + 20, amount_x - 70),
        "table_x_max": amount_x + 80,
    }


def _layout_region_clipped_row(row: dict[str, object], anchors: dict[str, float]) -> dict[str, object] | None:
    blocks = _layout_row_blocks(row)
    if not blocks:
        return None
    side_region_start_x = _layout_side_region_start_x(blocks)
    if _layout_table_header_row(row):
        kept_blocks = [
            block
            for block in blocks
            if anchors["table_x_min"] <= block.x <= anchors["table_x_max"]
        ]
    else:
        kept_blocks = []
        for block in blocks:
            text = block.text.strip()
            if not text:
                continue
            x = block.x
            if x < anchors["table_x_min"] or x > anchors["table_x_max"]:
                continue
            if x < anchors["description_x"]:
                kept_blocks.append(block)
                continue
            if x < anchors["amount_left"]:
                if (side_region_start_x is None or x < side_region_start_x) and not _layout_region_side_token(text):
                    kept_blocks.append(block)
                continue
            if _layout_region_amount_token(text):
                kept_blocks.append(block)

    if not kept_blocks:
        return None

    kept_blocks = sorted(kept_blocks, key=lambda block: block.x)
    tokens = [block.text.strip() for block in kept_blocks if block.text.strip()]
    text = _normalize_extracted_line(" ".join(tokens))
    if not text or _layout_noise_row(text):
        return None
    confidence_values = [block.confidence for block in kept_blocks if block.confidence is not None]
    clipped = dict(row)
    clipped["tokens"] = tokens
    clipped["token_confidences"] = [block.confidence for block in kept_blocks if block.text.strip()]
    clipped["text"] = text
    clipped["confidence"] = round(sum(confidence_values) / len(confidence_values) / 100, 3) if confidence_values else row["confidence"]
    clipped["blocks"] = kept_blocks
    clipped["region_detected"] = True
    clipped["region_excluded"] = len(kept_blocks) < len(blocks)
    return clipped


def _layout_region_reason_codes(row: dict[str, object]) -> list[str]:
    if not row.get("region_detected"):
        return []
    reason_codes = ["OCR_STATEMENT_REGION_DETECTED"]
    if row.get("region_excluded"):
        reason_codes.append("OCR_STATEMENT_REGION_EXCLUDED")
    return reason_codes


def _layout_side_region_start_x(blocks: list[object]) -> float | None:
    ordered = sorted(blocks, key=lambda block: block.x)
    for index, block in enumerate(ordered):
        for end_index in range(index + 1, min(len(ordered), index + 5) + 1):
            window = " ".join(item.text for item in ordered[index:end_index])
            match = SIDE_SUMMARY_PATTERN.search(window)
            if match and match.start() == 0:
                return block.x
    return None


def _layout_transaction_amount_x(row: dict[str, object]) -> float | None:
    tokens = row.get("tokens")
    if not isinstance(tokens, list) or not _layout_date_pair([str(token) for token in tokens]):
        return None
    blocks = _layout_row_blocks(row)
    for block in blocks[4:]:
        if LAYOUT_AMOUNT_PATTERN.match(block.text.strip().replace(" ", "")):
            return block.x
    return None


def _layout_row_blocks(row: dict[str, object]) -> list[object]:
    blocks = row.get("blocks")
    return blocks if isinstance(blocks, list) else []


def _layout_region_amount_token(text: str) -> bool:
    token = text.strip().replace(" ", "")
    if token.upper() in {"CR", "DR"}:
        return True
    return bool(LAYOUT_AMOUNT_PATTERN.match(token) or re.fullmatch(r"(?:PHP|USD|NZD|AUD|SGD|HKD|KRW|JPY)", token, re.IGNORECASE))


def _layout_region_side_token(text: str) -> bool:
    return bool(SIDE_SUMMARY_PATTERN.search(text)) or bool(
        re.fullmatch(
            r"(?:previous|statement|balance|payments?|credits?|purchases?|debits?|account|summary|payment|due|date|minimum|credit|limit|available|cash|interest|rate|rewards?|points?)",
            text.strip(),
            re.IGNORECASE,
        )
    )


def _layout_noise_row(text: str) -> bool:
    lowered = text.lower()
    return lowered in {"post tran", "date date", "description amount(php)", "continued on next page"}


def _layout_date_pair(tokens: list[str]) -> tuple[str, str] | None:
    if len(tokens) < 4:
        return None
    first = f"{tokens[0]} {tokens[1]}"
    second = f"{tokens[2]} {tokens[3]}"
    if DAY_MONTH_TOKEN_PATTERN.match(first) and DAY_MONTH_TOKEN_PATTERN.match(second):
        return first, second
    return None


def _last_layout_amount_token(tokens: list[str], confidences: list[object] | None = None) -> tuple[str, float, float | None] | None:
    confidence_values = confidences if isinstance(confidences, list) else []
    for index in range(len(tokens) - 1, -1, -1):
        token = tokens[index]
        normalized = token.replace(" ", "")
        match = LAYOUT_AMOUNT_PATTERN.match(normalized)
        if not match:
            continue
        amount = _try_parse_amount(match.group("amount"))
        if amount is None:
            continue
        if match.group("credit"):
            amount = -abs(amount)
        return token, amount, _token_confidence(confidence_values, index)
    return None


def _layout_amount_token_after_dates(
    tokens: list[str],
    confidences: list[object] | None = None,
) -> tuple[str, float, int, float | None] | None:
    confidence_values = confidences if isinstance(confidences, list) else []
    side_summary_index = _side_summary_token_index(tokens)
    amount_candidates: list[tuple[str, float, int, float | None]] = []
    search_tokens = tokens[4:side_summary_index] if side_summary_index is not None else tokens[4:]
    for index, token in enumerate(search_tokens, start=4):
        normalized = token.replace(" ", "")
        match = LAYOUT_AMOUNT_PATTERN.match(normalized)
        if not match:
            continue
        amount = _try_parse_amount(match.group("amount"))
        if amount is None:
            continue
        next_token = tokens[index + 1].upper() if index + 1 < len(tokens) else ""
        if match.group("credit") or next_token == "CR":
            amount = -abs(amount)
        amount_candidates.append((token, amount, index, _token_confidence(confidence_values, index)))
    return amount_candidates[-1] if amount_candidates else None


def _token_confidence(confidences: list[object], index: int) -> float | None:
    if index >= len(confidences) or confidences[index] is None:
        return None
    try:
        return round(float(confidences[index]) / 100, 3)
    except (TypeError, ValueError):
        return None


def _layout_row_parts_from_text(text: str) -> tuple[str, float, list[str]] | None:
    match = OCR_STATEMENT_DATE_PAIR_PATTERN.search(text)
    if not match:
        return None
    body = text[match.end() :].strip()
    if not body:
        return None
    transaction_body = SIDE_SUMMARY_PATTERN.split(body, maxsplit=1)[0].strip()
    amount_matches = list(AMOUNT_PATTERN.finditer(transaction_body))
    if not amount_matches:
        return None
    has_original_foreign_amount = bool(FOREIGN_CURRENCY_AMOUNT_PATTERN.search(transaction_body))
    amount_match = amount_matches[-1] if has_original_foreign_amount else amount_matches[0]
    amount_value = _try_parse_amount(amount_match.group(2))
    if amount_value is None:
        return None
    amount_end_window = transaction_body[amount_match.end() : amount_match.end() + 8].upper()
    reason_codes: list[str] = []
    if has_original_foreign_amount:
        reason_codes.append("BILLING_CURRENCY_AMOUNT_SELECTED")
    if re.match(r"^\s*CR\b", amount_end_window):
        amount_value = -abs(amount_value)
        reason_codes.append("CREDIT_MARKER_REPAIRED")
    description = _clean_reconstructed_description(_remove_original_foreign_amount(transaction_body[: amount_match.start()]))
    if not description:
        return None
    if transaction_body != body:
        reason_codes.append("SIDE_COLUMN_TEXT_EXCLUDED")
    return description, amount_value, reason_codes


def _remove_original_foreign_amount(text: str) -> str:
    return FOREIGN_CURRENCY_AMOUNT_PATTERN.sub("", text)


def _side_summary_token_index(tokens: list[str]) -> int | None:
    for index in range(len(tokens)):
        if SIDE_SUMMARY_PATTERN.search(" ".join(tokens[index : min(len(tokens), index + 4)])):
            return index
    return None


def _layout_description(tokens: list[str], date_pair: tuple[str, str], amount_text: str, amount_index: int | None) -> str:
    start_index = 4
    end_index = amount_index if amount_index is not None else len(tokens)
    description = " ".join(tokens[start_index:end_index])
    return _clean_reconstructed_description(description)


def _layout_continuation_text(text: str) -> bool:
    text = _strip_side_summary_text(text)
    if not text or _is_table_header_fragment(text) or _is_summary_description(text):
        return False
    lowered = text.lower()
    if any(term in lowered for term in ["by paying", "minimum amount", "outstanding balance", "interest", "charges", "please", "hsbc", "contact us"]):
        return False
    if _last_layout_amount_token(text.split()):
        return False
    return bool(re.search(r"[A-Za-z]{2,}", text))


def _layout_prefix_text(text: str) -> bool:
    text = _strip_side_summary_text(text)
    if not text or _is_table_header_fragment(text) or _is_summary_description(text):
        return False
    lowered = text.lower()
    if any(term in lowered for term in ["payment summary", "account summary", "credit limit", "interest rate", "please", "contact us", "by paying", "minimum amount", "outstanding balance", "charges"]):
        return False
    if _layout_noisy_description(text) or re.search(r"\b(?:X{4}|\*{4})\b|\d{4}[- ](?:X{4}|\*{4})", text, re.IGNORECASE):
        return False
    if DATE_PATTERN.search(text) or _last_layout_amount_token(text.split()):
        return False
    return bool(re.search(r"[A-Za-z]{2,}", text))


def _layout_side_column_text(text: str) -> bool:
    lowered = text.lower()
    return bool(SIDE_SUMMARY_PATTERN.search(text)) or any(
        term in lowered
        for term in ["by paying", "minimum amount", "outstanding balance", "interest", "charges", "please examine"]
    )


def _layout_suffix_fragment(text: str) -> bool:
    cleaned = _strip_side_summary_text(text).strip()
    if not cleaned:
        return False
    tokens = cleaned.split()
    upper_tokens = [token.upper().strip(".,") for token in tokens]
    if len(tokens) <= 1 and upper_tokens[0] in {"PH", "SG", "US", "NZ"}:
        return True
    return len(tokens) <= 4 and upper_tokens[-1:] in (["PH"], ["SG"], ["US"], ["NZ"])


def _strip_side_summary_text(text: str) -> str:
    return SIDE_SUMMARY_PATTERN.split(text, maxsplit=1)[0].strip()


def _remember_layout_prefix(pending_prefix: list[str], text: str) -> list[str]:
    # Keep only the nearest orphan fragment so stale text cannot leak into the next transaction row.
    cleaned = _strip_side_summary_text(text)
    return [*pending_prefix[-1:], cleaned][-1:] if cleaned else pending_prefix[-1:]


def _layout_noisy_description(text: str) -> bool:
    cleaned = re.sub(r"\b(?:PH|SG|CR)\b", "", text, flags=re.IGNORECASE).strip()
    letters = re.findall(r"[A-Za-z]", cleaned)
    words = re.findall(r"[A-Za-z]{2,}", cleaned)
    return len(cleaned) <= 4 or len(letters) < 3 or not words


def _append_layout_candidate(
    candidates: list[TransactionCandidate],
    active: dict[str, object],
    statement_year: int | None,
    document_type: str,
) -> None:
    amount_value = active.get("amount")
    description = _clean_reconstructed_description(" ".join(part for part in active.get("description_parts", []) if part))
    if amount_value is None or not description or _is_summary_description(description):
        return
    date_text = str(active.get("date_text") or "")
    posted_date_text = str(active.get("posted_date_text") or "")
    if (date_text and not _valid_day_month_text(date_text)) or (posted_date_text and not _valid_day_month_text(posted_date_text)):
        return
    source_text = str(active.get("source_text") or "")
    source = SourceReference(
        page_number=int(active.get("page_number") or 0),
        line_number=int(active.get("line_number") or len(candidates) + 1),
        text=source_text,
        section_id=f"section_{active.get('page_number') or 0}_transaction_table",
        section_label="transaction_table",
        source_text_redacted=_redact_sensitive(source_text),
        ocr_confidence=(
            active.get("amount_confidence")
            if isinstance(active.get("amount_confidence"), float)
            else active.get("confidence")
            if isinstance(active.get("confidence"), float)
            else None
        ),
        extraction_confidence=0.9,
    )
    reason_codes = ["OCR_LAYOUT_ROW_RECONSTRUCTED", "AMOUNT_DETECTED", "DATE_DETECTED", "DESCRIPTION_DETECTED"]
    active_reason_codes = list(dict.fromkeys(str(code) for code in active.get("reason_codes", []) if code))
    if active_reason_codes:
        reason_codes.append("OCR_LAYOUT_REPAIRED")
        reason_codes.extend(active_reason_codes)
    if statement_year:
        reason_codes.append("STATEMENT_YEAR_INFERRED")
    if document_type == "unknown":
        reason_codes.append("UNKNOWN_DOCUMENT_TYPE")
    candidates.append(
        TransactionCandidate(
            candidate_id=f"txn_{len(candidates) + 1:04d}",
            date_text=_with_statement_year(date_text, statement_year),
            posted_date_text=_with_statement_year(posted_date_text, statement_year),
            description=description,
            amount=abs(float(amount_value)),
            currency=settings.default_currency,
            direction="credit" if float(amount_value) < 0 else "debit",
            source=source,
            confidence=0.9 if document_type != "unknown" else 0.78,
            reason_codes=reason_codes,
        )
    )


def _mean_confidence(values: list[object]) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numeric) / len(numeric), 3) if numeric else 0.78


def _malformed_amount_findings(line_refs: list[SourceReference]) -> list[ExtractionFinding]:
    tokens = sorted({match.group(0) for line in line_refs for match in MALFORMED_AMOUNT_TOKEN_PATTERN.finditer(line.text)})
    if not tokens:
        return []
    return [
        ExtractionFinding(
            code="MALFORMED_AMOUNT_TOKEN",
            severity="warning",
            message=(
                "One or more OCR amount tokens used multiple decimal separators and required defensive handling: "
                f"{', '.join(tokens[:3])}"
            ),
        )
    ]


def _has_statement_shape_evidence(
    line_refs: list[SourceReference],
    fields: list[FinancialFieldCandidate],
    sections: list[SectionCandidate],
) -> bool:
    field_names = {field.field_name for field in fields if field.field_name in STATEMENT_SHAPE_FIELD_NAMES}
    if field_names & STATEMENT_EXCLUSIVE_FIELD_NAMES:
        return True
    if len(field_names) >= 3:
        return True

    section_labels = {section.section_label for section in sections}
    if "statement_summary" in section_labels and len(field_names) >= 2:
        return True

    text = " ".join(line.text.lower() for line in line_refs)
    statement_terms = {
        "statement date",
        "payment due date",
        "credit limit",
        "previous balance",
        "previous statement balance",
        "payments and credits",
        "payments & credits",
        "purchases and debits",
        "purchases & debits",
        "total account balance",
        "total amount due",
        "minimum amount due",
        "minimum payment",
        "statement of account",
    }
    hits = {term for term in statement_terms if term in text}
    exclusive_hits = hits & {
        "statement date",
        "previous statement balance",
        "payments and credits",
        "payments & credits",
        "purchases and debits",
        "purchases & debits",
        "total account balance",
    }
    if exclusive_hits and len(hits) >= 2:
        return True
    return len(hits) >= 3


def _extract_financial_fields(
    line_refs: list[SourceReference],
    min_confidence: float,
) -> list[FinancialFieldCandidate]:
    candidates: list[FinancialFieldCandidate] = []
    for line in line_refs:
        for field_name, pattern in STATEMENT_SUMMARY_PATTERNS.items():
            match = pattern.search(line.text)
            if not match:
                continue
            value_text = match.group(1).strip()
            amount_match = re.fullmatch(r"[0-9,]+\.\d{2}", value_text)
            normalized_value = f"{_parse_amount(value_text):.2f}" if amount_match else value_text
            candidates.append(
                FinancialFieldCandidate(
                    field_name=field_name,
                    field_label=field_name.replace("_", " ").title(),
                    value_type="amount" if amount_match else "date",
                    value_text=value_text,
                    normalized_value=normalized_value,
                    currency=settings.default_currency if amount_match else None,
                    source=line,
                    confidence=0.88,
                    reason_codes=["STATEMENT_SUMMARY_LABEL_DETECTED"],
                )
            )
        for field_name, (field_label, pattern) in FIELD_PATTERNS.items():
            match = pattern.search(line.text)
            if not match:
                continue

            value_text = match.group(1).strip()
            amount_match = AMOUNT_PATTERN.search(value_text)
            normalized_value = None
            currency = None
            reason_codes = ["FIELD_LABEL_DETECTED"]
            if field_name in {"statement_date", "payment_due_date"}:
                date_match = DATE_PATTERN.search(value_text)
                if not date_match:
                    continue
                normalized_value = date_match.group(0)
                reason_codes.append("DATE_DETECTED")
            elif amount_match:
                currency = _currency_code(amount_match.group(1))
                if currency == settings.default_currency:
                    currency = _infer_currency_from_text(line.text)
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
                    field_label=field_label,
                    value_type=_value_type(field_name, normalized_value),
                    value_text=value_text,
                    normalized_value=normalized_value,
                    currency=currency,
                    source=line,
                    confidence=0.86 if normalized_value else max(0.6, min_confidence),
                    reason_codes=reason_codes,
                )
            )
        candidates.extend(_receipt_total_amount_candidates(line))

    return candidates


def _receipt_total_amount_candidates(line: SourceReference) -> list[FinancialFieldCandidate]:
    candidates: list[FinancialFieldCandidate] = []
    for match in RECEIPT_TOTAL_AMOUNT_PATTERN.finditer(line.text):
        match_text = match.group(0)
        lookback = line.text[max(0, match.start() - 24):match.start()]
        if not re.search(r"\bsub\s*f?total|subfotal\b", match_text, re.IGNORECASE) and RECEIPT_TAX_ONLY_CONTEXT.search(
            f"{lookback} {match_text}"
        ):
            continue
        value_text = match.group(1).strip()
        candidates.append(
            FinancialFieldCandidate(
                field_name="receipt_total",
                field_label="Receipt Total",
                value_type="amount",
                value_text=value_text,
                normalized_value=f"{_parse_amount(value_text):.2f}",
                currency=_infer_currency_from_text(line.text),
                source=line,
                confidence=0.82,
                reason_codes=["RECEIPT_TOTAL_PRECEDENCE", "AMOUNT_DETECTED"],
            )
        )
    return candidates


def _derive_receipt_invoice_transactions(
    fields: list[FinancialFieldCandidate],
    line_refs: list[SourceReference],
    document_type: str,
) -> list[TransactionCandidate]:
    receipt_like_unknown = document_type == "unknown" and _looks_like_receipt_ocr(line_refs)
    if document_type not in {"receipt", "invoice"} and not receipt_like_unknown:
        return []

    document_date = _receipt_document_date(line_refs)
    preferred_names = ["purchase_amount", "card_receipt_amount"]
    for field_name in preferred_names:
        field = _best_financial_field(fields, field_name)
        if not field or field.value_type != "amount":
            continue
        return [
            _field_derived_transaction(
                field=field,
                amount=float(field.normalized_value or 0),
                currency=_receipt_field_currency(field),
                description=_receipt_invoice_description(field.source, "receipt" if receipt_like_unknown else document_type),
                date_text=document_date,
                reason_code="RECEIPT_TOTAL_TRANSACTION_DERIVED",
                confidence=0.68 if receipt_like_unknown else 0.74,
            )
        ]

    repaired_payment_amount = _receipt_payment_method_amount(line_refs)
    if repaired_payment_amount:
        amount, source = repaired_payment_amount
        return [
            _field_derived_transaction(
                field=None,
                amount=amount,
                currency=_infer_currency_from_text(source.text),
                description=_receipt_invoice_description(source, "receipt" if receipt_like_unknown else document_type),
                source=source,
                date_text=document_date,
                reason_code="RECEIPT_PAYMENT_AMOUNT_REPAIRED",
                confidence=0.62,
            )
        ]

    if document_type == "receipt" or receipt_like_unknown:
        repaired_labelled_total = _receipt_labelled_total_amount(line_refs)
        if repaired_labelled_total:
            amount, source, reason_code = repaired_labelled_total
            return [
                _field_derived_transaction(
                    field=None,
                    amount=amount,
                    currency=_infer_currency_from_text(source.text),
                    description=_receipt_invoice_description(source, "receipt" if receipt_like_unknown else document_type),
                    source=source,
                    date_text=document_date,
                    reason_code=reason_code,
                    confidence=0.66 if receipt_like_unknown else 0.72,
                )
            ]

    for field_name in ["receipt_total", "total_amount_due"]:
        field = _best_financial_field(fields, field_name)
        if not field or field.value_type != "amount":
            continue
        return [
            _field_derived_transaction(
                field=field,
                amount=float(field.normalized_value or 0),
                currency=_receipt_field_currency(field),
                description=_receipt_invoice_description(field.source, "receipt" if receipt_like_unknown else document_type),
                date_text=document_date,
                reason_code="RECEIPT_TOTAL_TRANSACTION_DERIVED",
                confidence=0.68 if receipt_like_unknown else 0.74,
            )
        ]

    if document_type == "invoice":
        computed = _computed_invoice_item_total(line_refs)
        if computed:
            amount, source = computed
            return [
                _field_derived_transaction(
                    field=None,
                    amount=amount,
                    currency=_infer_currency_from_text(source.text),
                    description=_receipt_invoice_description(source, document_type),
                    source=source,
                    date_text=document_date,
                    confidence=0.68,
                    reason_code="INVOICE_LINE_ITEM_TOTAL_DERIVED",
                )
            ]

    return []


def _best_financial_field(fields: list[FinancialFieldCandidate], field_name: str) -> FinancialFieldCandidate | None:
    candidates = [field for field in fields if field.field_name == field_name and field.normalized_value]
    if not candidates:
        return None
    candidates.sort(key=_financial_field_priority, reverse=True)
    return candidates[0]


def _receipt_field_currency(field: FinancialFieldCandidate) -> str:
    inferred = _infer_currency_from_text(field.source.text if field.source else "")
    if field.currency and field.currency != settings.default_currency:
        return field.currency
    return inferred


def _financial_field_priority(field: FinancialFieldCandidate) -> tuple[int, float]:
    if "RECEIPT_TOTAL_PRECEDENCE" in field.reason_codes:
        return (4, field.confidence)
    if "FIELD_LABEL_DETECTED" in field.reason_codes:
        return (2, field.confidence)
    return (1, field.confidence)


def _looks_like_receipt_ocr(line_refs: list[SourceReference]) -> bool:
    text = " ".join(line.text for line in line_refs).lower()
    evidence = [
        "tax invoice",
        "receipt",
        "total",
        "subtotal",
        "gst",
        "tax",
        "include tax",
        "eftpos",
        "ef tpos",
        "purchase",
        "approved",
        "card",
        "terminal",
    ]
    return sum(1 for term in evidence if term in text) >= 3


def _receipt_labelled_total_amount(line_refs: list[SourceReference]) -> tuple[float, SourceReference, str] | None:
    text = "\n".join(line.text for line in line_refs)
    if not text.strip():
        return None

    label_patterns = [
        ("RECEIPT_COMPLETE_TOTAL_REPAIRED", r"\b(?:complete|approved)\b\s*[:;-]?\s*"),
        ("RECEIPT_CARD_TOTAL_REPAIRED", r"\b(?:bank|flank|debit|credit)\s+card\b\s*[:;-]?\s*"),
        ("RECEIPT_LABELLED_TOTAL_REPAIRED", r"\b(?:grand\s+total|total|amount\s+due|due\s+amount)\b\s*[:;-]?\s*"),
        ("RECEIPT_EFTPOS_TOTAL_REPAIRED", r"\b(?:eftpos|ef\s*tpos)\b\s*[:;-]?\s*"),
    ]
    for reason_code, label_pattern in label_patterns:
        for match in re.finditer(label_pattern, text, re.IGNORECASE):
            context_start = max(0, match.start() - 24)
            context = text[context_start : min(len(text), match.end() + 56)]
            if re.search(r"\b(?:include|included|includes|gst|tax)\b.{0,12}\b(?:total|amount)\b", context, re.IGNORECASE):
                continue
            amount_match = re.search(
                r"(?:NZD|NZ\$|\$|PHP|USD|AUD)?\s*([0-9]{1,4}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2}))(?![\d.])",
                context[match.start() - context_start :],
                re.IGNORECASE,
            )
            if amount_match:
                amount = _try_parse_amount(amount_match.group(1))
                if amount is None:
                    continue
                if amount > 0:
                    source = _source_for_text_window(line_refs, match.start(), context)
                    return amount, source, reason_code

            repaired_amount = _repaired_receipt_amount_from_label_context(context[match.start() - context_start :])
            if repaired_amount:
                amount, repair_reason = repaired_amount
                source = _source_for_text_window(line_refs, match.start(), context)
                return amount, source, repair_reason
    return None


def _repaired_receipt_amount_from_label_context(context: str) -> tuple[float, str] | None:
    compact_nzd = re.search(
        r"\bNZD\s*0?([1-9]\d{1,3})\s*(?:[.,]\s*)?(?:O[0OF]?|[O0]F|G[O0]|[O0]{1,2})\b",
        context,
        re.IGNORECASE,
    )
    if compact_nzd:
        return float(compact_nzd.group(1)), "RECEIPT_DAMAGED_TOTAL_REPAIRED"

    split_total = re.search(
        r"(?:NZD|NZ\$|\$)?\s*0?([1-9]\d{1,3})\s+([0-9O]{2})\b",
        context,
        re.IGNORECASE,
    )
    if split_total:
        cents = split_total.group(2).upper().replace("O", "0")
        return float(f"{split_total.group(1)}.{cents}"), "RECEIPT_DAMAGED_TOTAL_REPAIRED"

    alpha_decimal = re.search(
        r"(?:NZD|NZ\$|\$)?\s*0?([1-9]\d{1,3})\s*[.,]\s*[A-Z]{1,3}\b",
        context,
        re.IGNORECASE,
    )
    if alpha_decimal:
        return float(alpha_decimal.group(1)), "RECEIPT_DAMAGED_TOTAL_REPAIRED"

    return None


def _source_for_text_window(line_refs: list[SourceReference], absolute_start: int, fallback_text: str) -> SourceReference:
    offset = 0
    for line in line_refs:
        line_length = len(line.text) + 1
        if offset <= absolute_start < offset + line_length:
            return SourceReference(
                page_number=line.page_number,
                line_number=line.line_number,
                text=line.text,
                section_id=line.section_id,
                section_label=line.section_label or "receipt_totals",
                source_text_redacted=line.source_text_redacted,
                ocr_confidence=line.ocr_confidence,
                extraction_confidence=line.extraction_confidence,
            )
        offset += line_length
    cleaned = fallback_text.strip()
    return SourceReference(
        page_number=None,
        line_number=1,
        text=cleaned,
        section_label="receipt_totals",
        source_text_redacted=_redact_sensitive(cleaned),
    )


def _receipt_document_date(line_refs: list[SourceReference]) -> str | None:
    text = " ".join(line.text for line in line_refs)
    labelled = re.search(r"\b(?:date|issued|printed)\s*[:;-]?\s*", text, re.IGNORECASE)
    if labelled:
        for labelled_match in DATE_PATTERN.finditer(text, labelled.end()):
            if labelled_match.start() - labelled.end() > 50:
                break
            if not _plausible_date_text(labelled_match.group(0)):
                continue
            return labelled_match.group(0)

    terminal_date = re.search(
        rf"\b(?:terminal|fermin[a-z]*|eftpos|ef\s*tpo|receipt|customer)\b.{{0,120}}?({DAY_MONTH_YEAR_PATTERN.pattern})",
        text,
        re.IGNORECASE,
    )
    if terminal_date:
        normalized_terminal_date = _format_day_month_year(terminal_date)
        if normalized_terminal_date:
            return normalized_terminal_date

    textual_date = DAY_MONTH_YEAR_PATTERN.search(text)
    if textual_date:
        normalized_textual_date = _format_day_month_year(textual_date)
        if normalized_textual_date:
            return normalized_textual_date

    compact_textual_date = COMPACT_DAY_MONTH_YEAR_PATTERN.search(text)
    if compact_textual_date:
        normalized_compact_date = _format_day_month_year(compact_textual_date)
        if normalized_compact_date:
            return normalized_compact_date

    for match in DATE_PATTERN.finditer(text):
        if _plausible_date_text(match.group(0)):
            return match.group(0)

    short_match = SHORT_NUMERIC_DATE_PATTERN.search(text)
    year = _receipt_year_hint(text)
    if short_match and year:
        return f"{int(short_match.group('day')):02d}/{int(short_match.group('month')):02d}/{year}"
    if short_match:
        return short_match.group(0)
    return None


def _plausible_date_text(value: str) -> bool:
    numeric = re.match(r"^\s*(?P<first>\d{1,2})[/-](?P<second>\d{1,2})[/-](?P<year>\d{2,4})\s*$", value)
    if not numeric:
        return True
    first = int(numeric.group("first"))
    second = int(numeric.group("second"))
    return 1 <= first <= 31 and 1 <= second <= 12


def _format_day_month_year(match: re.Match[str]) -> str | None:
    day = int(match.group("day"))
    month_text = match.group("month").lower()[:4]
    month = MONTH_NUMBERS.get(month_text) or MONTH_NUMBERS.get(month_text[:3])
    if not month:
        return None
    year_text = match.group("year")
    year = int(f"20{year_text}" if len(year_text) == 2 else year_text)
    return f"{day:02d}/{month:02d}/{year}"


def _receipt_year_hint(text: str) -> str | None:
    year_match = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if year_match:
        return year_match.group(1)
    month_year_match = MONTH_YEAR_PATTERN.search(text)
    if month_year_match:
        year_text = month_year_match.group("year")
        return f"20{year_text}" if len(year_text) == 2 else year_text
    return None


def _receipt_payment_method_amount(line_refs: list[SourceReference]) -> tuple[float, SourceReference] | None:
    for line in line_refs:
        if line.section_label not in {"receipt_totals", "payment_proof", "unknown_financial_block"}:
            continue
        match = re.search(
            r"\b(?:bank|flank|debit|credit)\s+card\b.{0,30}(?<!\d)([0-9]{2,3}(?:,\d{3})*(?:\.\s?\d{2}|,\d{2}))(?![\d.])",
            line.text,
            re.IGNORECASE,
        )
        if match:
            return _parse_amount(match.group(1)), line
    return None


def _field_derived_transaction(
    field: FinancialFieldCandidate | None,
    amount: float,
    currency: str,
    description: str,
    reason_code: str,
    source: SourceReference | None = None,
    date_text: str | None = None,
    confidence: float = 0.74,
) -> TransactionCandidate:
    source_ref = source or (field.source if field else None)
    return TransactionCandidate(
        candidate_id="txn_0001",
        date_text=date_text or _derived_transaction_date(source_ref.text if source_ref else None),
        posted_date_text=None,
        description=description,
        amount=round(abs(amount), 2),
        currency=currency,
        direction="debit",
        source=source_ref
        or SourceReference(
            page_number=None,
            line_number=1,
            text=description,
            section_label="receipt_totals",
            source_text_redacted=_redact_sensitive(description),
        ),
        confidence=confidence,
        reason_codes=[reason_code, "AMOUNT_DETECTED", "OCR_RECEIPT_TOTAL_FALLBACK"],
    )


def _computed_invoice_item_total(line_refs: list[SourceReference]) -> tuple[float, SourceReference] | None:
    for line in line_refs:
        if line.section_label not in {"invoice_summary", "receipt_totals"}:
            continue
        item_block = re.split(r"\b(?:total\s+gst|payment\s+history|paid|owing)\b", line.text, maxsplit=1, flags=re.IGNORECASE)[0]
        amounts = [amount for _, amount in _amounts(item_block)]
        if len(amounts) < 2:
            continue
        return round(sum(abs(amount) for amount in amounts), 2), line
    return None


def _receipt_invoice_description(source: SourceReference | None, document_type: str) -> str:
    if not source:
        return f"{document_type.title()} payment"
    text = source.text
    receipt_description = _receipt_sale_description(text)
    if receipt_description:
        return receipt_description[:120]
    stop_terms = r"\b(?:MID|TRAN|RRN|AID|TAX INVOICE|INVOICE|ISSUED|PRODUCT|PAYMENT HISTORY|EFTPOS|PURCHASE|TOTAL)\b"
    prefix = re.split(stop_terms, text, maxsplit=1, flags=re.IGNORECASE)[0]
    cleaned = _clean_reconstructed_description(prefix)
    return cleaned[:120] or f"{document_type.title()} payment"


def _receipt_sale_description(text: str) -> str | None:
    merchant_description = _known_receipt_merchant_description(text)
    if merchant_description:
        return merchant_description

    sale_match = re.search(
        r"\b((?:unregistered|registered)?\s*[A-Z][A-Za-z0-9 ]{0,40}?\s+(?:money|iioney)?\s*(?:sale|purchase|top\s*up|reload|payment|fare))\b",
        text,
        re.IGNORECASE,
    )
    location_match = re.search(
        r"\b(?:station|store|branch|location|merchant)\s+(?:name|nane|id)?\s*[:;-]?\s*([A-Z][A-Za-z0-9 .'-]{1,40})",
        text,
        re.IGNORECASE,
    )
    sale_text = _clean_receipt_description_text(sale_match.group(1)) if sale_match else None
    location_text = _clean_receipt_description_text(location_match.group(1)) if location_match else None
    if sale_text and location_text and location_text.lower() not in sale_text.lower():
        return f"{sale_text} - {location_text}"
    return sale_text or location_text


def _known_receipt_merchant_description(text: str) -> str | None:
    lowered = text.lower()
    if "bunnings" in lowered or "gunn ihs" in lowered:
        if "self checkout" in lowered:
            return "Bunnings - Self Checkout"
        return "Bunnings"

    if "awanui" in lowered and re.search(r"\b(?:purchase|eftpos|approved)\b", text, re.IGNORECASE):
        location_match = re.search(r"\bAwanui\s+([A-Za-z ]{2,32}?)(?:\s+\d{1,4}\b|\s+MID\b|\s+New Zealand\b)", text, re.IGNORECASE)
        if location_match:
            location = _clean_receipt_description_text(location_match.group(1)).title()
            return f"Awanui - Card purchase - {location}"
        return "Awanui - Card purchase"

    if re.search(r"\bsan\s+(?:nichelle|michelle)\s+bags\b", text, re.IGNORECASE):
        product_match = re.search(r"/\s*([A-Za-z][A-Za-z0-9 /-]{2,60}?)(?:\s+QTY|\s+\d+\s*@|\s+\$)", text, re.IGNORECASE)
        if product_match:
            product = _clean_receipt_description_text(product_match.group(1)).title()
            return f"San Michelle Bags - {product}"
        return "San Michelle Bags"

    if re.search(r"\b(?:a)?wanui\s+labs?\b", text, re.IGNORECASE):
        service_match = re.search(r"\bCC\s+CRE\s*-\s*([A-Za-z][A-Za-z ]{2,50})\s+\$", text, re.IGNORECASE)
        if service_match:
            service = _clean_receipt_description_text(service_match.group(1))
            return f"Awanui Labs - {service}"
        return "Awanui Labs"

    return None


def _clean_receipt_description_text(text: str) -> str:
    cleaned = re.sub(r"\biioney\b", "money", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^.*?\b(unregistered|registered)\b", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:date|time|equipment|shift|card|end|fee|added|new|due|amount|payment|id)\b.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = _clean_reconstructed_description(cleaned)
    return cleaned.title() if cleaned.isupper() else cleaned


def _derived_transaction_date(text: str | None) -> str | None:
    if not text:
        return None
    match = DATE_PATTERN.search(text)
    return match.group(0) if match else None


def _infer_currency_from_text(text: str) -> str:
    if re.search(r"\b(?:NZD|NZ0|NZ\$|N[Z2]\$|NZ[A-Z0-9$]{0,2}\s*\d)", text, re.IGNORECASE):
        return "NZD"
    if re.search(
        r"\b(?:New Zealand|Auckland|Wellington|EFTPOS|EFT\s+CARD|Bunnings|Kmart|Woolworths|HOP|Awanui)\b",
        text,
        re.IGNORECASE,
    ):
        return "NZD"
    return settings.default_currency


def _extract_statement_table_rows(
    line_refs: list[SourceReference],
    document_type: str,
) -> list[TransactionCandidate]:
    normalized_refs = [_normalized_source_reference(line) for line in line_refs]
    statement_year = _statement_year(normalized_refs)
    start_index = _transaction_table_start(normalized_refs)
    if start_index is None:
        return []

    candidates: list[TransactionCandidate] = []
    index = start_index
    while index < len(normalized_refs):
        line = normalized_refs[index]
        text = line.text.strip()
        if _is_table_stop(text):
            break
        combined = _combined_statement_row_candidate(
            line=line,
            text=text,
            statement_year=statement_year,
            document_type=document_type,
            candidate_number=len(candidates) + 1,
        )
        if combined:
            candidates.append(combined)
            index += 1
            continue
        continued = _combined_statement_continuation_row_candidate(
            line=line,
            text=text,
            next_line=normalized_refs[index + 1] if index + 1 < len(normalized_refs) else None,
            statement_year=statement_year,
            document_type=document_type,
            candidate_number=len(candidates) + 1,
        )
        if continued:
            candidates.append(continued)
            index += 2
            continue
        if not MONTH_DAY_PATTERN.match(text):
            index += 1
            continue
        if index + 1 >= len(normalized_refs) or not MONTH_DAY_PATTERN.match(normalized_refs[index + 1].text.strip()):
            index += 1
            continue

        transaction_date_text = _with_statement_year(text, statement_year)
        posted_date_text = _with_statement_year(normalized_refs[index + 1].text.strip(), statement_year)
        row_source = line
        index += 2
        description_parts: list[str] = []
        amount_value: float | None = None
        amount_currency = settings.default_currency

        while index < len(normalized_refs):
            current = normalized_refs[index]
            current_text = current.text.strip()
            if _is_table_stop(current_text):
                break
            if MONTH_DAY_PATTERN.match(current_text) and amount_value is None:
                break
            if _is_single_amount_text(current_text):
                amount_currency, amount_value = _amounts(current_text)[-1]
                index += 1
                break
            if not _should_skip_table_description(current_text):
                description_parts.append(current_text)
            index += 1

        if amount_value is None or not description_parts:
            continue

        description = _clean_reconstructed_description(" ".join(description_parts))
        if not description or _is_summary_description(description):
            continue

        source_text = f"{text} {normalized_refs[index - 1].text if index > 0 else ''} {description}"
        source = SourceReference(
            page_number=row_source.page_number,
            line_number=row_source.line_number,
            text=source_text.strip(),
            section_id=f"section_{row_source.page_number or 0}_transaction_table",
            section_label="transaction_table",
            source_text_redacted=_redact_sensitive(source_text.strip()),
            extraction_confidence=0.9,
        )
        reason_codes = ["TABLE_ROW_RECONSTRUCTED", "AMOUNT_DETECTED", "DATE_DETECTED", "DESCRIPTION_DETECTED"]
        if statement_year:
            reason_codes.append("STATEMENT_YEAR_INFERRED")
        if document_type == "unknown":
            reason_codes.append("UNKNOWN_DOCUMENT_TYPE")

        candidates.append(
            TransactionCandidate(
                candidate_id=f"txn_{len(candidates) + 1:04d}",
                date_text=transaction_date_text,
                posted_date_text=posted_date_text,
                description=description,
                amount=abs(amount_value),
                currency=(amount_currency or settings.default_currency).upper(),
                direction=_direction(description, amount_value),
                source=source,
                confidence=0.9 if document_type != "unknown" else 0.78,
                reason_codes=reason_codes,
            )
        )

    return candidates


def _extract_flattened_statement_rows(
    line_refs: list[SourceReference],
    document_type: str,
) -> list[TransactionCandidate]:
    if _canonical_document_type(document_type) not in {"statement", "unknown"}:
        return []

    normalized_refs = [_normalized_source_reference(line) for line in line_refs]
    statement_year = _statement_year(normalized_refs)
    candidates: list[TransactionCandidate] = []

    for line in normalized_refs:
        text = line.text.strip()
        if len(text) < 120 or not _looks_like_flattened_statement_text(text):
            continue

        matches = list(OCR_STATEMENT_DATE_PAIR_PATTERN.finditer(text))
        if not matches:
            continue

        for match_index, match in enumerate(matches):
            next_start = matches[match_index + 1].start() if match_index + 1 < len(matches) else min(len(text), match.end() + 180)
            segment = text[match.end() : next_start].strip()
            if not segment or _is_table_stop(segment) or _is_summary_description(segment):
                continue

            amount_match = AMOUNT_PATTERN.search(segment)
            if not amount_match:
                continue

            amount_value = _try_parse_amount(amount_match.group(2))
            if amount_value is None:
                continue
            amount_currency = _currency_code(amount_match.group(1))
            amount_end_window = segment[amount_match.end() : amount_match.end() + 4].upper()
            if amount_end_window.startswith("CR"):
                amount_value = -abs(amount_value)

            before_amount = segment[: amount_match.start()].strip(" -|")
            after_amount = segment[amount_match.end() :].strip(" -|")
            description = _clean_flattened_statement_description(before_amount, after_amount)
            if not description or _is_summary_description(description):
                continue

            source_text = f"{match.group(0)} {segment[:160]}".strip()
            source = SourceReference(
                page_number=line.page_number,
                line_number=line.line_number,
                text=source_text,
                section_id=f"section_{line.page_number or 0}_transaction_table",
                section_label="transaction_table",
                source_text_redacted=_redact_sensitive(source_text),
                extraction_confidence=0.74,
            )
            reason_codes = ["OCR_FLATTENED_ROW_RECONSTRUCTED", "AMOUNT_DETECTED", "DATE_DETECTED"]
            if statement_year:
                reason_codes.append("STATEMENT_YEAR_INFERRED")
            if document_type == "unknown":
                reason_codes.append("UNKNOWN_DOCUMENT_TYPE")

            candidates.append(
                TransactionCandidate(
                    candidate_id=f"txn_{len(candidates) + 1:04d}",
                    date_text=_with_statement_year(match.group("date_text"), statement_year),
                    posted_date_text=_with_statement_year(match.group("posted_date_text"), statement_year),
                    description=description,
                    amount=abs(amount_value),
                    currency=(amount_currency or settings.default_currency).upper(),
                    direction=_direction(f"{description} {amount_end_window}", amount_value),
                    source=source,
                    confidence=0.74 if document_type != "unknown" else 0.64,
                    reason_codes=reason_codes,
                )
            )

    return candidates


def _combined_statement_row_candidate(
    line: SourceReference,
    text: str,
    statement_year: int | None,
    document_type: str,
    candidate_number: int,
) -> TransactionCandidate | None:
    match = COMBINED_STATEMENT_ROW_PATTERN.match(text)
    if not match:
        return None
    description = _clean_reconstructed_description(match.group("description"))
    if not description or _is_summary_description(description):
        return None
    amounts = _amounts(match.group("amount"))
    if not amounts:
        return None
    amount_currency, amount_value = amounts[-1]
    source = SourceReference(
        page_number=line.page_number,
        line_number=line.line_number,
        text=text,
        section_id=f"section_{line.page_number or 0}_transaction_table",
        section_label="transaction_table",
        source_text_redacted=_redact_sensitive(text),
        extraction_confidence=0.88,
    )
    reason_codes = ["TABLE_ROW_RECONSTRUCTED", "AMOUNT_DETECTED", "DATE_DETECTED", "DESCRIPTION_DETECTED"]
    if statement_year:
        reason_codes.append("STATEMENT_YEAR_INFERRED")
    if document_type == "unknown":
        reason_codes.append("UNKNOWN_DOCUMENT_TYPE")
    return TransactionCandidate(
        candidate_id=f"txn_{candidate_number:04d}",
        date_text=_with_statement_year(match.group("date_text"), statement_year),
        posted_date_text=_with_statement_year(match.group("posted_date_text"), statement_year),
        description=description,
        amount=abs(amount_value),
        currency=(amount_currency or settings.default_currency).upper(),
        direction="credit" if amount_value < 0 else "debit",
        source=source,
        confidence=0.88 if document_type != "unknown" else 0.76,
        reason_codes=reason_codes,
    )


def _combined_statement_continuation_row_candidate(
    line: SourceReference,
    text: str,
    next_line: SourceReference | None,
    statement_year: int | None,
    document_type: str,
    candidate_number: int,
) -> TransactionCandidate | None:
    match = COMBINED_STATEMENT_ROW_WITHOUT_AMOUNT_PATTERN.match(text)
    if not match or next_line is None:
        return None

    next_text = next_line.text.strip()
    if (
        not next_text
        or MONTH_DAY_PATTERN.match(next_text)
        or COMBINED_STATEMENT_ROW_PATTERN.match(next_text)
        or COMBINED_STATEMENT_ROW_WITHOUT_AMOUNT_PATTERN.match(next_text)
        or _is_table_stop(next_text)
    ):
        return None

    amounts = _amounts(next_text)
    if not amounts:
        return None

    description = _clean_reconstructed_description(match.group("description"))
    if not description or _is_summary_description(description):
        return None

    amount_currency, amount_value = amounts[-1]
    source_text = f"{text} {next_text}".strip()
    source = SourceReference(
        page_number=line.page_number,
        line_number=line.line_number,
        text=source_text,
        section_id=f"section_{line.page_number or 0}_transaction_table",
        section_label="transaction_table",
        source_text_redacted=_redact_sensitive(source_text),
        extraction_confidence=0.86,
    )
    reason_codes = ["TABLE_ROW_RECONSTRUCTED", "AMOUNT_DETECTED", "DATE_DETECTED", "DESCRIPTION_DETECTED"]
    if len(amounts) > 1:
        reason_codes.append("BILLING_CURRENCY_AMOUNT_SELECTED")
    if statement_year:
        reason_codes.append("STATEMENT_YEAR_INFERRED")
    if document_type == "unknown":
        reason_codes.append("UNKNOWN_DOCUMENT_TYPE")

    return TransactionCandidate(
        candidate_id=f"txn_{candidate_number:04d}",
        date_text=_with_statement_year(match.group("date_text"), statement_year),
        posted_date_text=_with_statement_year(match.group("posted_date_text"), statement_year),
        description=description,
        amount=abs(amount_value),
        currency=(amount_currency or settings.default_currency).upper(),
        direction="credit" if amount_value < 0 else "debit",
        source=source,
        confidence=0.86 if document_type != "unknown" else 0.74,
        reason_codes=reason_codes,
    )


def _extract_sections(line_refs: list[SourceReference]) -> list[SectionCandidate]:
    sections: dict[str, SectionCandidate] = {}
    for line in line_refs:
        label = line.section_label or "unknown_financial_block"
        key = f"{line.page_number or 0}:{label}"
        if key not in sections:
            sections[key] = SectionCandidate(
                section_id=line.section_id or f"section_{len(sections) + 1:03d}",
                section_label=label,
                page_number=line.page_number,
                first_line_number=line.line_number,
                last_line_number=line.line_number,
                source_text_redacted=line.source_text_redacted or _redact_sensitive(line.text),
                confidence=0.78 if label != "unknown_financial_block" else 0.55,
                reason_codes=["SECTION_KEYWORD_DETECTED"] if label != "unknown_financial_block" else ["UNKNOWN_SECTION_CONTEXT"],
            )
            continue
        section = sections[key]
        section.last_line_number = line.line_number
        if len(section.source_text_redacted) < 240:
            section.source_text_redacted = f"{section.source_text_redacted} {_redact_sensitive(line.text)}"[:240]
    return list(sections.values())


def _extract_entities(line_refs: list[SourceReference], document_type: str) -> list[EntityCandidate]:
    candidates: list[EntityCandidate] = []
    full_text = " ".join(line.text for line in line_refs[:20])
    issuer_match = re.search(r"\b(HSBC|BPI|BDO|Metrobank|Security Bank|Awanui Labs?|AwanuiLabs)\b", full_text, re.IGNORECASE)
    if issuer_match:
        candidates.append(
            EntityCandidate(
                entity_id=f"entity_{len(candidates) + 1:04d}",
                entity_type="issuer_or_provider_name",
                value_text=issuer_match.group(1),
                normalized_value=issuer_match.group(1).upper() if issuer_match.group(1).lower() != "awanu labs" else issuer_match.group(1).title(),
                source=line_refs[0],
                confidence=0.82,
                reason_codes=["ISSUER_OR_PROVIDER_TEXT_DETECTED"],
            )
        )
    product_match = re.search(r"\b([A-Z][A-Z ]{2,40}\s+(?:VISA|MASTERCARD|CARD))\b", full_text, re.IGNORECASE)
    if product_match:
        candidates.append(
            EntityCandidate(
                entity_id=f"entity_{len(candidates) + 1:04d}",
                entity_type="card_product",
                value_text=product_match.group(1).strip(),
                normalized_value=product_match.group(1).strip().title(),
                source=line_refs[0],
                confidence=0.72,
                reason_codes=["CARD_PRODUCT_TEXT_DETECTED"],
            )
        )
    currency_match = re.search(r"\b(?:AMOUNT|Credit Limit|Available Credit)\s*\((PHP|USD|NZD|AUD)\)\b", full_text, re.IGNORECASE)
    if currency_match:
        candidates.append(
            EntityCandidate(
                entity_id=f"entity_{len(candidates) + 1:04d}",
                entity_type="currency",
                value_text=currency_match.group(1).upper(),
                normalized_value=currency_match.group(1).upper(),
                source=line_refs[0],
                confidence=0.86,
                reason_codes=["CURRENCY_LABEL_DETECTED"],
            )
        )
    for line in line_refs[:5]:
        if re.search(r"\b(bank|credit cards?|financial institution|statement issuer)\b", line.text, re.IGNORECASE):
            candidates.append(
                EntityCandidate(
                    entity_id=f"entity_{len(candidates) + 1:04d}",
                    entity_type="institution_name",
                    value_text=_entity_phrase(line.text),
                    normalized_value=_entity_phrase(line.text).title(),
                    source=line,
                    confidence=0.74,
                    reason_codes=["INSTITUTION_KEYWORD_DETECTED"],
                )
            )
            break
        if document_type in {"receipt", "invoice"} and not _amounts(line.text):
            candidates.append(
                EntityCandidate(
                    entity_id=f"entity_{len(candidates) + 1:04d}",
                    entity_type="merchant_or_provider_name",
                    value_text=line.text[:120],
                    normalized_value=line.text[:120].title(),
                    source=line,
                    confidence=0.62,
                    reason_codes=["DOCUMENT_HEADER_CANDIDATE"],
                )
            )
            break
    return candidates


def _extract_references(fields: list[FinancialFieldCandidate], line_refs: list[SourceReference]) -> list[ReferenceCandidate]:
    references: list[ReferenceCandidate] = []
    for field in fields:
        if field.field_name not in REFERENCE_FIELD_NAMES:
            continue
        value = field.normalized_value or field.value_text
        references.append(
            ReferenceCandidate(
                reference_id=f"ref_{len(references) + 1:04d}",
                reference_type=field.field_name,
                value_text=field.value_text,
                normalized_value=_mask_reference(value),
                masked=_mask_reference(value) != value,
                source=field.source,
                confidence=field.confidence,
                reason_codes=[*field.reason_codes, "REFERENCE_FIELD_DETECTED"],
            )
        )
    for line in line_refs[:30]:
        for match in re.finditer(r"\b\d{4}-X{4}-X{4}-\d{4}\b|\b\d{4}[- ]\*{4}[- ]\*{4}[- ]\d{4}\b", line.text, re.IGNORECASE):
            value = match.group(0)
            references.append(
                ReferenceCandidate(
                    reference_id=f"ref_{len(references) + 1:04d}",
                    reference_type="masked_card_number",
                    value_text=value,
                    normalized_value=value,
                    masked=True,
                    source=line,
                    confidence=0.88,
                    reason_codes=["MASKED_CARD_REFERENCE_DETECTED"],
                )
            )
    return references


def _extract_line_items(line_refs: list[SourceReference]) -> list[LineItemCandidate]:
    items: list[LineItemCandidate] = []
    for line in line_refs:
        if line.section_label not in {"line_items", "receipt_totals", "invoice_summary"}:
            continue
        amounts = _amounts(line.text)
        if not amounts or re.search(r"\b(total|gst|paid|owing|purchase|approved)\b", line.text, re.IGNORECASE):
            continue
        items.append(
            LineItemCandidate(
                line_item_id=f"item_{len(items) + 1:04d}",
                description=_description_without_amounts(line.text),
                amount=abs(amounts[-1][1]),
                currency=amounts[-1][0] or settings.default_currency,
                source=line,
                confidence=0.62,
                reason_codes=["LINE_ITEM_AMOUNT_DETECTED"],
            )
        )
    return items


def _document_type(request: TransactionExtractionRequest) -> str:
    if request.document_type:
        return _canonical_document_type(request.document_type)
    if request.classification and request.classification.document_type:
        return _canonical_document_type(request.classification.document_type)
    return "unknown"


def _canonical_document_type(document_type: str | None) -> str:
    normalized = (document_type or "unknown").lower()
    if normalized == "bank_statement":
        return "statement"
    if normalized == "transfer_proof":
        return "payment_proof"
    return normalized


def _upstream_quality_findings(request: TransactionExtractionRequest) -> list[ExtractionFinding]:
    findings: list[ExtractionFinding] = []
    if request.quality and request.quality.low_text:
        findings.append(
            ExtractionFinding(
                code="LOW_TEXT_QUALITY_INPUT",
                severity="warning",
                message="Upstream parsing reported low extracted text quality; extraction candidates may be incomplete.",
            )
        )

    upstream_codes = {finding.code for finding in request.findings}
    if "NO_TEXT_EXTRACTED" in upstream_codes:
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_NO_TEXT_EXTRACTED",
                severity="warning",
                message="Upstream parsing completed without usable extracted text.",
            )
        )
    if "OCR_FALLBACK_DISABLED" in upstream_codes:
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_DISABLED",
                severity="warning",
                message="Upstream parsing needed OCR but OCR was disabled; rerun parsing with OCR enabled before expecting reliable extraction.",
            )
        )
    if upstream_codes.intersection({"TESSERACT_UNAVAILABLE", "PDF_RENDERER_UNAVAILABLE", "OCR_FAILED"}):
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_FAILURE",
                severity="warning",
                message="Upstream parsing reported an OCR runtime or processing failure; fix OCR readiness before retrying extraction.",
            )
        )
    if upstream_codes.intersection({"LOW_OCR_CONFIDENCE", "OCR_TEXT_NOISY"}):
        findings.append(
            ExtractionFinding(
                code="UPSTREAM_OCR_QUALITY_WEAK",
                severity="warning",
                message="Upstream parsing reported weak OCR text quality; extraction candidates may be incomplete or unreliable.",
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
                    refs.append(_source_reference(page.page_number, line_number, line.strip()))
        return refs

    return [
        _source_reference(None, line_number, line.strip())
        for line_number, line in enumerate(text.splitlines(), start=1)
        if line.strip()
    ]


def _source_reference(page_number: int | None, line_number: int, text: str) -> SourceReference:
    section_label = _section_label(text)
    source = SourceReference(
        page_number=page_number,
        line_number=line_number,
        text=text,
        section_id=f"section_{page_number or 0}_{section_label}",
        section_label=section_label,
        source_text_redacted=_redact_sensitive(text),
    )
    return source


def _normalized_source_reference(source: SourceReference) -> SourceReference:
    text = _normalize_extracted_line(source.text)
    section_label = "transaction_table" if _looks_like_transaction_table_text(text) else _section_label(text)
    return SourceReference(
        page_number=source.page_number,
        line_number=source.line_number,
        text=text,
        section_id=f"section_{source.page_number or 0}_{section_label}",
        section_label=section_label,
        source_text_redacted=_redact_sensitive(text),
        ocr_confidence=source.ocr_confidence,
        extraction_confidence=source.extraction_confidence,
    )


def _normalize_extracted_line(text: str) -> str:
    stripped = " ".join(text.split())
    if not stripped:
        return stripped
    tokens = stripped.split(" ")
    singleish = [token for token in tokens if len(token) == 1 or re.fullmatch(r"[:/.,()-]+", token)]
    if len(tokens) >= 4 and len(singleish) / len(tokens) >= 0.55:
        stripped = "".join(tokens)
    stripped = re.sub(r"([A-Za-z])(\d)", r"\1 \2", stripped)
    stripped = re.sub(r"(\d)([A-Za-z])", r"\1 \2", stripped)
    stripped = re.sub(r"\s+([:/.,])", r"\1", stripped)
    stripped = re.sub(r"([:])(?=\d)", r"\1 ", stripped)
    stripped = re.sub(r"\bMa:", "Ma:", stripped, flags=re.IGNORECASE)
    return " ".join(stripped.split())


def _looks_like_transaction_table_text(text: str) -> bool:
    lowered = text.lower()
    return bool(MONTH_DAY_PATTERN.match(text) or _is_single_amount_text(text) or any(term in lowered for term in TABLE_HEADER_TERMS))


def _statement_year(line_refs: list[SourceReference]) -> int | None:
    for line in line_refs:
        if "statement date" not in line.text.lower() and "document date" not in line.text.lower():
            continue
        match = DATE_PATTERN.search(line.text)
        if match:
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", match.group(0))
            if year_match:
                return int(year_match.group(1))
    for line in line_refs:
        match = DATE_PATTERN.search(line.text)
        if match:
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", match.group(0))
            if year_match:
                return int(year_match.group(1))
    return None


def _transaction_table_start(line_refs: list[SourceReference]) -> int | None:
    for index, line in enumerate(line_refs):
        header_line = line.text.lower()
        if not (
            "transaction" in header_line
            or "post" in header_line
            or "description" in header_line
            or _is_table_header_fragment(line.text)
        ):
            continue
        window = " ".join(ref.text.lower() for ref in line_refs[index : index + 8])
        if "transaction" in window and "description" in window and "amount" in window:
            start = index + 1
            header_scan_limit = min(len(line_refs), index + 8)
            while start < header_scan_limit and _is_table_header_text(line_refs[start].text):
                start += 1
            return start
    for index in range(len(line_refs) - 2):
        if MONTH_DAY_PATTERN.match(line_refs[index].text) and MONTH_DAY_PATTERN.match(line_refs[index + 1].text):
            return index
    return None


def _is_table_header_text(text: str) -> bool:
    lowered = text.strip().lower()
    return _is_table_header_fragment(text) or any(term in lowered for term in TABLE_HEADER_TERMS)


def _is_table_header_fragment(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in TABLE_HEADER_TERMS or lowered in {"post", "posting", "transaction date", "post date"}


def _is_table_stop(text: str) -> bool:
    return bool(TABLE_STOP_PATTERN.search(text))


def _is_table_hard_stop(text: str) -> bool:
    return bool(TABLE_HARD_STOP_PATTERN.search(text))


def _should_skip_table_description(text: str) -> bool:
    return bool(TABLE_SKIP_PATTERN.search(text)) or _is_table_header_fragment(text)


def _is_single_amount_text(text: str) -> bool:
    amounts = _amounts(text)
    return len(amounts) == 1 and not re.search(r"[A-Za-z]{3,}", AMOUNT_PATTERN.sub("", text))


def _with_statement_year(month_day_text: str, statement_year: int | None) -> str:
    if statement_year is None or DATE_PATTERN.search(month_day_text):
        return month_day_text
    return f"{month_day_text} {statement_year}"


def _looks_like_flattened_statement_text(text: str) -> bool:
    lowered = text.lower()
    if "amount" not in lowered and "balance" not in lowered:
        return False
    return len(OCR_STATEMENT_DATE_PAIR_PATTERN.findall(text)) >= 2


def _clean_reconstructed_description(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip(" -|")
    cleaned = re.sub(r"\bMa\s*:", "MA:", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([:/])", r"\1", cleaned)
    cleaned = re.sub(r"([:])\s+", r"\1 ", cleaned)
    cleaned = re.sub(r"\b([A-Za-z]+)-([A-Za-z]+)", lambda match: f"{match.group(1)}-{match.group(2)}", cleaned)
    return cleaned.strip()


def _clean_flattened_statement_description(before_amount: str, after_amount: str) -> str:
    if before_amount and len(before_amount.split()) >= 2:
        candidate = before_amount
    else:
        candidate = after_amount

    candidate = re.split(
        r"\b(?:continued on next page|payment due date|credit limit|cash limit|available credit|monthly interest rate|minimum payment|purchases? & debits|payments? & credits|total account balance|outstanding installments)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    candidate = re.sub(r"\b(?:PH|SG|VA|PHP|USD|NZD|CR)\b$", "", candidate.strip(), flags=re.IGNORECASE)
    return _clean_reconstructed_description(candidate)


def _is_summary_description(text: str) -> bool:
    lowered = text.lower()
    return any(
        term in lowered
        for term in [
            "finance charge",
            "previous balance",
            "past due",
            "ending balance",
            "unbilled installment amount",
            "total outstanding balance",
            "credit limit",
            "amount due",
            "account summary",
            "payment summary",
        ]
    )


def _amounts(text: str) -> list[tuple[str | None, float]]:
    amounts: list[tuple[str | None, float]] = []
    for match in AMOUNT_PATTERN.finditer(text):
        amount = _try_parse_amount(match.group(2))
        if amount is None:
            continue
        amounts.append((_currency_code(match.group(1)), amount))
    return amounts


def _parse_amount(value: str) -> float:
    normalized = value.replace(" ", "")
    if normalized.count(".") > 1 and "," not in normalized:
        whole, cents = normalized.rsplit(".", 1)
        whole_parts = whole.split(".")
        if len(cents) == 2 and all(part.isdigit() for part in whole_parts) and all(len(part) == 3 for part in whole_parts[1:]):
            normalized = f"{''.join(whole_parts)}.{cents}"
    if "," in normalized and "." not in normalized and re.search(r",\d{2}$", normalized):
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    return float(normalized)


def _try_parse_amount(value: str) -> float | None:
    try:
        return _parse_amount(value)
    except (TypeError, ValueError):
        return None


def _currency_code(value: str | None) -> str:
    if not value:
        return settings.default_currency
    normalized = value.upper()
    if normalized in {"$", "NZ$"}:
        return "NZD" if normalized == "NZ$" else settings.default_currency
    return normalized


def _description_without_amounts(text: str) -> str:
    return AMOUNT_PATTERN.sub("", text).strip(" -|")


def _section_label(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ["statement date", "amount due", "credit limit", "outstanding balance", "previous balance"]):
        return "statement_summary"
    if any(term in lowered for term in ["payment due", "past due", "finance charge", "late payment", "interest rate"]):
        return "fees_or_interest" if "charge" in lowered or "interest" in lowered else "statement_summary"
    if any(term in lowered for term in ["confirmation no", "transfer amount", "transfer from", "transfer to"]):
        return "payment_proof"
    if any(term in lowered for term in ["invoice", "paid", "owing", "total gst", "includes gst"]):
        return "invoice_summary"
    if any(term in lowered for term in ["receipt", "eftpos", "purchase", "approved", "merchant"]):
        return "receipt_totals"
    if any(term in lowered for term in ["points", "rewards"]):
        return "rewards_or_points"
    if DATE_PATTERN.search(text) and _amounts(text):
        return "transaction_table"
    if _amounts(text):
        return "unknown_financial_block"
    return "unknown_financial_block"


def _redact_sensitive(text: str) -> str:
    redacted = re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "****-****-****-****", text)
    redacted = re.sub(r"\b\d{6,}\b", lambda match: f"***{match.group(0)[-4:]}", redacted)
    return redacted[:500]


def _value_type(field_name: str, normalized_value: str | None) -> str:
    if field_name.endswith("_date"):
        return "date"
    if field_name in REFERENCE_FIELD_NAMES:
        return "reference"
    if normalized_value and re.fullmatch(r"-?\d+(?:\.\d{2})?", normalized_value):
        return "amount"
    return "text"


def _separate_statement_payment_and_installments(
    transactions: list[TransactionCandidate],
    line_refs: list[SourceReference],
) -> tuple[list[FinancialFieldCandidate], list[InstallmentCandidate], list[TransactionCandidate]]:
    fields: list[FinancialFieldCandidate] = []
    installments: list[InstallmentCandidate] = []
    kept_transactions: list[TransactionCandidate] = []

    for candidate in transactions:
        context = _nearby_source_context(line_refs, candidate.source)
        if _is_statement_payment_credit(candidate):
            fields.append(_statement_payment_field(candidate))
            continue
        if _is_installment_purchase_principal(candidate, context):
            installments.append(_installment_candidate(candidate, len(installments) + 1))
            continue
        kept_transactions.append(candidate)

    return fields, installments, kept_transactions


def _repair_statement_purchase_gap_transactions(
    *,
    request: TransactionExtractionRequest,
    transactions: list[TransactionCandidate],
    fields: list[FinancialFieldCandidate],
    document_type: str,
    line_refs: list[SourceReference],
) -> list[TransactionCandidate]:
    purchases_and_debits = _best_field_amount(fields, "purchases_and_debits")
    if purchases_and_debits is None or purchases_and_debits <= 0:
        return []

    rows = _layout_rows(request)
    if not rows:
        return []

    statement_year = _statement_year(line_refs)
    statement_start = _statement_period_start(line_refs)
    repaired_rows = _hsbc_reconciliation_repair_rows(
        rows=rows,
        purchases_and_debits=purchases_and_debits,
        statement_year=statement_year,
        statement_start=statement_start,
        document_type=document_type,
    )
    if not repaired_rows:
        return []

    repaired_total = round(sum(candidate.amount for candidate in repaired_rows if candidate.direction == "debit"), 2)
    if abs(repaired_total - purchases_and_debits) > 0.01:
        return []

    current_debits = [candidate for candidate in transactions if candidate.direction == "debit"]
    current_total = round(sum(candidate.amount for candidate in current_debits), 2)
    suspicious_current = any(_suspicious_statement_total_candidate(candidate, purchases_and_debits) for candidate in current_debits)
    if len(repaired_rows) <= len(current_debits) and abs(current_total - purchases_and_debits) <= 0.01 and not suspicious_current:
        return []

    preserved_rows = [candidate for candidate in transactions if candidate.direction != "debit"]
    return _renumber_transaction_candidates([*repaired_rows, *preserved_rows])


def _renumber_transaction_candidates(candidates: list[TransactionCandidate]) -> list[TransactionCandidate]:
    renumbered: list[TransactionCandidate] = []
    for index, candidate in enumerate(candidates, start=1):
        renumbered.append(candidate.model_copy(update={"candidate_id": f"txn_{index:04d}"}))
    return renumbered


def _hsbc_reconciliation_repair_rows(
    *,
    rows: list[dict[str, object]],
    purchases_and_debits: float,
    statement_year: int | None,
    statement_start: str | None,
    document_type: str,
) -> list[TransactionCandidate]:
    parsed_debits: list[dict[str, object]] = []
    damaged_rows: list[dict[str, object]] = []
    in_transaction_table = False

    for row in rows:
        text = str(row["text"])
        if _layout_grid_header_row(row):
            in_transaction_table = True
            continue
        if not in_transaction_table:
            continue
        if (re.search(r"\btotal\s+due\b", text, re.IGNORECASE) and (parsed_debits or damaged_rows)) or _is_table_hard_stop(text):
            break
        parsed = _hsbc_repair_row(row)
        if not parsed:
            continue
        if parsed["kind"] == "payment":
            continue
        if parsed["kind"] == "debit":
            parsed_debits.append(parsed)
        elif parsed["kind"] == "damaged_debit":
            damaged_rows.append(parsed)

    known_total = round(sum(float(row["amount"]) for row in parsed_debits), 2)
    missing_amount = round(purchases_and_debits - known_total, 2)
    if len(damaged_rows) != 1 or missing_amount <= 0.01:
        return []
    if missing_amount > purchases_and_debits or missing_amount < 1:
        return []

    repaired = [*parsed_debits, {**damaged_rows[0], "amount": missing_amount, "amount_repaired": True}]
    repaired.sort(key=lambda item: (int(item["page_number"]), int(item["line_number"])))

    candidates: list[TransactionCandidate] = []
    for item in repaired:
        _append_repaired_statement_candidate(
            candidates,
            item,
            statement_year=statement_year,
            statement_start=statement_start,
            document_type=document_type,
        )
    return candidates


def _hsbc_repair_row(row: dict[str, object]) -> dict[str, object] | None:
    blocks = sorted(_layout_row_blocks(row), key=lambda block: block.x)
    if len(blocks) < 5:
        return None

    side_start_x = _layout_side_region_start_x(blocks)
    table_blocks = [
        block
        for block in blocks
        if 80 <= block.x <= 760 and (side_start_x is None or block.x < side_start_x)
    ]
    if len(table_blocks) < 5:
        return None

    text = _normalize_extracted_line(" ".join(block.text.strip() for block in table_blocks if block.text.strip()))
    lowered = text.lower()
    if not re.search(r"[A-Za-z]{3,}", text):
        return None
    if _is_summary_description(text) or _layout_side_column_text(text):
        return None

    amount_match = _hsbc_repair_amount(table_blocks)
    description = _hsbc_repair_description(table_blocks, amount_match[0] if amount_match else None)
    if not description or _is_summary_description(description):
        return None

    date_pair = _layout_grid_date_pair(table_blocks) or _hsbc_fuzzy_date_pair(table_blocks)
    if "paid thru" in lowered or re.search(r"\bpaid\b", lowered):
        return {"kind": "payment"}

    if date_pair and amount_match:
        _amount_index, _amount_text, amount_value, amount_confidence = amount_match
        return {
            "kind": "debit",
            "page_number": int(row["page_number"]),
            "line_number": int(row["line_number"]),
            "date_text": date_pair[0],
            "posted_date_text": date_pair[1],
            "description": description,
            "amount": amount_value,
            "source_text": text,
            "confidence": row["confidence"],
            "amount_confidence": amount_confidence,
            "reason_codes": ["OCR_TABLE_GRID_ROW_RECONSTRUCTED", "OCR_TABLE_GRID_FUZZY_DATE_REPAIRED"],
        }

    if amount_match and _hsbc_damaged_merchant_description(description):
        return {
            "kind": "damaged_debit",
            "page_number": int(row["page_number"]),
            "line_number": int(row["line_number"]),
            "date_text": None,
            "posted_date_text": None,
            "description": description,
            "source_text": text,
            "confidence": min(float(row.get("confidence") or 0.68), 0.72),
            "amount_confidence": amount_match[3],
            "reason_codes": [
                "OCR_TABLE_GRID_DAMAGED_DATE",
                "OCR_TABLE_GRID_DAMAGED_AMOUNT",
                "STATEMENT_PURCHASE_TOTAL_REPAIR",
            ],
        }
    return None


def _hsbc_repair_amount(blocks: list[object]) -> tuple[int, str, float, float | None] | None:
    amount_candidates: list[tuple[int, str, float, float | None, float]] = []
    for index, block in enumerate(blocks):
        if block.x < 600 or block.x > 760:
            continue
        token = block.text.strip()
        match = LAYOUT_AMOUNT_PATTERN.match(token.replace(" ", ""))
        if not match:
            continue
        amount = _try_parse_amount(match.group("amount"))
        if amount is None:
            continue
        if match.group("credit") or token.upper().endswith("CR"):
            amount = -abs(amount)
        amount_candidates.append((index, token, amount, _token_confidence([block.confidence], 0), block.x))
    positive_candidates = [candidate for candidate in amount_candidates if candidate[2] > 0]
    selected = positive_candidates[0] if positive_candidates else (amount_candidates[0] if amount_candidates else None)
    if not selected:
        return None
    return selected[0], selected[1], selected[2], selected[3]


def _hsbc_repair_description(blocks: list[object], amount_index: int | None) -> str:
    end_index = amount_index if amount_index is not None else len(blocks)
    description_blocks = [
        block
        for block in blocks
        if 285 <= block.x < 600
        and blocks.index(block) < end_index
        and (_layout_grid_description_token(block.text, block.x) or _hsbc_description_number_token(block.text))
    ]
    return _clean_reconstructed_description(" ".join(block.text.strip() for block in description_blocks))


def _hsbc_description_number_token(token: str) -> bool:
    return bool(re.fullmatch(r"\d+(?:st|nd|rd|th)?", token.strip(), re.IGNORECASE))


def _hsbc_fuzzy_date_pair(blocks: list[object]) -> tuple[str, str, int, int, float] | None:
    first = _hsbc_fuzzy_date_in_band(blocks, 90, 180)
    second = _hsbc_fuzzy_date_in_band(blocks, 190, 290)
    if not first or not second:
        return None
    return first[0], second[0], first[1], second[1], second[2]


def _hsbc_fuzzy_date_in_band(blocks: list[object], x_min: float, x_max: float) -> tuple[str, int, float] | None:
    band = [(index, block) for index, block in enumerate(blocks) if x_min <= block.x <= x_max]
    day: str | None = None
    day_index: int | None = None
    month: str | None = None
    end_x = 0.0
    for index, block in band:
        token = block.text.strip()
        compact = COMPACT_DAY_MONTH_TOKEN_PATTERN.match(token)
        if compact and _valid_day_month_parts(compact.group("day"), compact.group("month")):
            return f"{compact.group('day')} {compact.group('month')}", index, block.x + block.width
        if day is None and re.fullmatch(r"\d{1,2}", token) and 1 <= int(token) <= 31:
            day = token
            day_index = index
        if _layout_month_token(token):
            month = token
            end_x = block.x + block.width
    if day and month and day_index is not None and _valid_day_month_parts(day, month):
        return f"{day} {month}", day_index, end_x
    return None


def _hsbc_damaged_merchant_description(description: str) -> bool:
    lowered = description.lower()
    if any(term in lowered for term in ["previous", "statement", "balance", "account summary", "total due"]):
        return False
    words = re.findall(r"[A-Za-z]{2,}", description)
    return len(words) >= 2


def _append_repaired_statement_candidate(
    candidates: list[TransactionCandidate],
    item: dict[str, object],
    *,
    statement_year: int | None,
    statement_start: str | None,
    document_type: str,
) -> None:
    date_text = item.get("date_text")
    posted_date_text = item.get("posted_date_text")
    if not date_text and item.get("amount_repaired") and statement_start:
        date_text = statement_start
    source_text = str(item.get("source_text") or "")
    reason_codes = [
        "OCR_LAYOUT_ROW_RECONSTRUCTED",
        "AMOUNT_DETECTED",
        "DESCRIPTION_DETECTED",
        *[str(code) for code in item.get("reason_codes", [])],
    ]
    if date_text:
        reason_codes.append("DATE_DETECTED")
    if item.get("amount_repaired"):
        reason_codes.append("AMOUNT_REPAIRED_FROM_STATEMENT_TOTAL")
    if statement_year:
        reason_codes.append("STATEMENT_YEAR_INFERRED")
    if document_type == "unknown":
        reason_codes.append("UNKNOWN_DOCUMENT_TYPE")

    source = SourceReference(
        page_number=int(item.get("page_number") or 0),
        line_number=int(item.get("line_number") or len(candidates) + 1),
        text=source_text,
        section_id=f"section_{item.get('page_number') or 0}_transaction_table",
        section_label="transaction_table",
        source_text_redacted=_redact_sensitive(source_text),
        ocr_confidence=(
            item.get("amount_confidence")
            if isinstance(item.get("amount_confidence"), float)
            else item.get("confidence")
            if isinstance(item.get("confidence"), float)
            else None
        ),
        extraction_confidence=0.72 if item.get("amount_repaired") else 0.86,
    )
    candidates.append(
        TransactionCandidate(
            candidate_id=f"txn_{len(candidates) + 1:04d}",
            date_text=_with_statement_year(str(date_text), statement_year) if date_text else None,
            posted_date_text=_with_statement_year(str(posted_date_text), statement_year) if posted_date_text else None,
            description=str(item["description"]),
            amount=abs(float(item["amount"])),
            currency=settings.default_currency,
            direction="debit",
            source=source,
            confidence=0.64 if item.get("amount_repaired") else 0.86,
            reason_codes=list(dict.fromkeys(reason_codes)),
        )
    )


def _suspicious_statement_total_candidate(candidate: TransactionCandidate, purchases_and_debits: float) -> bool:
    text = f"{candidate.description} {candidate.source.text}".lower()
    if abs(candidate.amount - purchases_and_debits) > 0.01:
        return False
    return bool(re.search(r"\b(paid thru|payments?|credits?|total)\b", text))


def _statement_period_start(line_refs: list[SourceReference]) -> str | None:
    for line in line_refs:
        match = re.search(r"\bstatement\s+from\s+(" + DAY_MONTH_FRAGMENT + r")\b", line.text, re.IGNORECASE)
        if match and _valid_day_month_text(match.group(1)):
            return match.group(1)
    return None


def _is_statement_payment_credit(candidate: TransactionCandidate) -> bool:
    description = candidate.description.lower()
    source_text = candidate.source.text.lower()
    combined = f"{description} {source_text}"
    has_payment_marker = bool(re.search(r"\bpaid\s+thru\b|\bpaid\s+through\b|\bpayment\s+(?:received|posted|credited)\b", combined))
    if has_payment_marker and candidate.direction == "credit":
        return True
    if has_payment_marker and _source_has_matching_credit_amount(candidate):
        return True
    if re.search(r"\b(?:payment|paid)\b", combined) and _source_has_matching_credit_amount(candidate):
        return True
    return candidate.direction == "credit" and bool(re.search(r"\b(payment|paid)\b", description))


def _source_has_matching_credit_amount(candidate: TransactionCandidate) -> bool:
    source_text = candidate.source.text if candidate.source else ""
    for match in re.finditer(r"\b(?P<amount>\d{1,3}(?:,\d{3})*(?:\.\d{2}|,\d{2}))\s*cr\b", source_text, re.IGNORECASE):
        amount = _try_parse_amount(match.group("amount"))
        if amount is not None and abs(amount - candidate.amount) <= 0.01:
            return True
    return False


def _flattened_statement_payment_fields(
    line_refs: list[SourceReference],
    existing_fields: list[FinancialFieldCandidate],
) -> list[FinancialFieldCandidate]:
    if any(field.field_name == "payments_and_credits" for field in existing_fields):
        return []

    fields: list[FinancialFieldCandidate] = []
    pattern = re.compile(
        r"\b(?P<label>(?:paid|payment)[A-Z0-9\s/&.-]{0,80}?)\s+(?P<amount>[0-9,]+\.\d{2})\s*CR\b",
        re.IGNORECASE,
    )
    for line in line_refs:
        for match in pattern.finditer(line.text):
            value = _parse_amount(match.group("amount"))
            fields.append(
                FinancialFieldCandidate(
                    field_name="payments_and_credits",
                    field_label="Payments And Credits",
                    value_type="amount",
                    value_text=f"{value:.2f}",
                    normalized_value=f"{value:.2f}",
                    currency=settings.default_currency,
                    source=_source_with_section(line, "statement_summary"),
                    confidence=0.72,
                    reason_codes=["OCR_FLATTENED_PAYMENT_FIELD_RECONSTRUCTED", "AMOUNT_DETECTED"],
                )
            )
    return fields


def _statement_payment_field(candidate: TransactionCandidate) -> FinancialFieldCandidate:
    return FinancialFieldCandidate(
        field_name="payments_and_credits",
        field_label="Payments And Credits",
        value_type="amount",
        value_text=f"{candidate.amount:.2f}",
        normalized_value=f"{candidate.amount:.2f}",
        currency=candidate.currency,
        source=_source_with_section(candidate.source, "statement_summary"),
        confidence=candidate.confidence,
        reason_codes=[*candidate.reason_codes, "STATEMENT_PAYMENT_CREDIT_FIELD"],
    )


def _is_installment_purchase_principal(candidate: TransactionCandidate, context: str) -> bool:
    lowered = context.lower()
    if "installment purchase" not in lowered:
        return False
    amortization_index = lowered.rfind("installment amortization")
    purchase_index = lowered.rfind("installment purchase")
    return purchase_index > amortization_index


def _installment_candidate(candidate: TransactionCandidate, index: int) -> InstallmentCandidate:
    return InstallmentCandidate(
        installment_id=f"installment_{index:04d}",
        purchase_date_text=candidate.date_text,
        posted_date_text=candidate.posted_date_text,
        description=candidate.description,
        principal_amount=candidate.amount,
        currency=candidate.currency,
        term_text=_installment_term(candidate.description),
        source=_source_with_section(candidate.source, "installment_balances"),
        confidence=round(min(candidate.confidence, 0.86), 3),
        reason_codes=[*candidate.reason_codes, "INSTALLMENT_PURCHASE_PRINCIPAL"],
    )


def _installment_term(text: str) -> str | None:
    match = re.search(r"\b\d{1,2}\s*/\s*\d{1,2}\b", text)
    return match.group(0).replace(" ", "") if match else None


def _nearby_source_context(line_refs: list[SourceReference], source: SourceReference) -> str:
    if source.line_number <= 0:
        return source.text
    lines = [
        line.text
        for line in line_refs
        if line.page_number == source.page_number and source.line_number - 4 <= line.line_number <= source.line_number
    ]
    return " ".join(lines) if lines else source.text


def _source_with_section(source: SourceReference, section_label: str) -> SourceReference:
    return SourceReference(
        page_number=source.page_number,
        line_number=source.line_number,
        text=source.text,
        section_id=source.section_id,
        section_label=section_label,
        source_text_redacted=source.source_text_redacted,
        ocr_confidence=source.ocr_confidence,
        extraction_confidence=source.extraction_confidence,
    )


def _looks_like_non_transaction_financial_block(text: str, amounts: list[tuple[str | None, float]]) -> bool:
    if len(text) > 300 and len(amounts) >= 3:
        return True
    lowered = text.lower()
    if any(term in lowered for term in ["statement of account", "credit limit", "minimum amount due", "outstanding balance"]):
        return True
    if any(term in lowered for term in ["interest rate", "finance charge", "important advisory"]):
        return True
    return False


def _entity_phrase(text: str) -> str:
    phrase = re.split(r"\b(?:Prepared for|Statement of Account|Statement)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return phrase[:120].strip()


def _mask_reference(value: str) -> str:
    return re.sub(r"\d(?=\d{4})", "*", value)


def _direction(text: str, amount: float) -> str:
    lowered = text.lower()
    if amount < 0 or re.search(r"\bcr\b", lowered) or any(word in lowered for word in ["payment", "received", "deposit", "reversal"]):
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
    sections: list[SectionCandidate],
    entities: list[EntityCandidate],
    references: list[ReferenceCandidate],
    line_items: list[LineItemCandidate],
    installments: list[InstallmentCandidate],
    findings: list[ExtractionFinding],
    min_confidence: float,
    pages_processed: int,
    text_length: int,
) -> TransactionExtractionResult:
    finding_counts = dict(Counter(finding.code for finding in findings))
    debit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "debit"), 2)
    credit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "credit"), 2)
    amount_total = round(sum(candidate.amount for candidate in transactions), 2)
    reconciliation = _reconcile_statement(transactions, fields)
    low_confidence_count = sum(
        1
        for candidate in [*transactions, *fields, *installments]
        if candidate.confidence < min_confidence
    )

    summary = ExtractionSummary(
        transaction_candidate_count=len(transactions),
        financial_field_candidate_count=len(fields),
        section_candidate_count=len(sections),
        entity_candidate_count=len(entities),
        reference_candidate_count=len(references),
        line_item_candidate_count=len(line_items),
        installment_candidate_count=len(installments),
        debit_total=debit_total,
        credit_total=credit_total,
        amount_total=amount_total,
        pages_processed=pages_processed,
        text_length=text_length,
        low_confidence_candidate_count=low_confidence_count,
        reconciliation_status=reconciliation.status,
    )
    evaluation = ExtractionEvaluation(
        extraction_id=extraction_id,
        parse_id=request.parse_id,
        document_type=document_type,
        status=status,
        transaction_candidate_count=len(transactions),
        financial_field_candidate_count=len(fields),
        section_candidate_count=len(sections),
        entity_candidate_count=len(entities),
        reference_candidate_count=len(references),
        line_item_candidate_count=len(line_items),
        installment_candidate_count=len(installments),
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
        classification=request.classification,
        transaction_candidates=transactions,
        financial_field_candidates=fields,
        section_candidates=sections,
        entity_candidates=entities,
        reference_candidates=references,
        line_item_candidates=line_items,
        installment_candidates=installments,
        quality_metadata=QualityMetadata(
            text_length=text_length,
            pages_processed=pages_processed,
            low_text_input=bool(request.quality and request.quality.low_text),
            upstream_finding_codes=[finding.code for finding in request.findings],
        ),
        reconciliation=reconciliation,
        document_tables=_document_tables(
            request=request,
            document_type=document_type,
            transactions=transactions,
            fields=fields,
            entities=entities,
            references=references,
            installments=installments,
            reconciliation=reconciliation,
            findings=findings,
        ),
        summary=summary,
        evaluation=evaluation,
        findings=findings,
    )


def _reconcile_statement(
    transactions: list[TransactionCandidate],
    fields: list[FinancialFieldCandidate],
) -> ReconciliationResult:
    previous_balance = _first_not_none(
        _best_field_amount(fields, "previous_statement_balance"),
        _best_field_amount(fields, "previous_balance"),
    )
    payments_and_credits = _best_field_amount(fields, "payments_and_credits")
    purchases_and_debits = _best_field_amount(fields, "purchases_and_debits")
    total_due = _first_not_none(
        _best_field_amount(fields, "total_due"),
        _best_field_amount(fields, "total_amount_due"),
    )
    debit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "debit"), 2)
    credit_total = round(sum(candidate.amount for candidate in transactions if candidate.direction == "credit"), 2)
    effective_credit_total = payments_and_credits if payments_and_credits is not None else credit_total
    computed_total_due = round((previous_balance or 0) + debit_total - effective_credit_total, 2) if previous_balance is not None else None
    purchase_difference = round(debit_total - purchases_and_debits, 2) if purchases_and_debits is not None else None
    purchase_mismatch = purchase_difference is not None and abs(purchase_difference) > 0.01

    if previous_balance is None or total_due is None:
        return ReconciliationResult(
            status="needs_review" if purchase_mismatch else "not_available",
            previous_balance=previous_balance,
            debit_total=debit_total,
            credit_total=effective_credit_total,
            total_due=total_due,
            computed_total_due=computed_total_due,
            reason_codes=["SUMMARY_FIELDS_INCOMPLETE", "PURCHASE_TOTAL_MISMATCH"] if purchase_mismatch else ["SUMMARY_FIELDS_INCOMPLETE"],
        )

    difference = round((computed_total_due or 0) - total_due, 2)
    reason_codes: list[str] = []
    if abs(difference) <= 0.01:
        reason_codes.append("STATEMENT_TOTAL_RECONCILED")
    else:
        reason_codes.append("STATEMENT_TOTAL_MISMATCH")
    if purchase_mismatch:
        reason_codes.append("PURCHASE_TOTAL_MISMATCH")
    return ReconciliationResult(
        status="matched" if abs(difference) <= 0.01 and not purchase_mismatch else "needs_review",
        previous_balance=previous_balance,
        debit_total=debit_total,
        credit_total=effective_credit_total,
        total_due=total_due,
        computed_total_due=computed_total_due,
        difference=difference,
        reason_codes=reason_codes,
    )


def _reconciliation_review_findings(
    transactions: list[TransactionCandidate],
    fields: list[FinancialFieldCandidate],
) -> list[ExtractionFinding]:
    reconciliation = _reconcile_statement(transactions, fields)
    findings: list[ExtractionFinding] = []
    purchases_and_debits = _best_field_amount(fields, "purchases_and_debits")
    if "PURCHASE_TOTAL_MISMATCH" in reconciliation.reason_codes and purchases_and_debits is not None:
        difference = round((reconciliation.debit_total or 0) - purchases_and_debits, 2)
        findings.append(
            ExtractionFinding(
                code="STATEMENT_PURCHASE_TOTAL_MISMATCH",
                severity="warning",
                message=(
                    "Extracted debit transactions do not match the statement purchases/debits total "
                    f"(extracted {reconciliation.debit_total:.2f}, statement {purchases_and_debits:.2f}, difference {difference:.2f})."
                ),
            )
        )
    if "STATEMENT_TOTAL_MISMATCH" in reconciliation.reason_codes:
        findings.append(
            ExtractionFinding(
                code="STATEMENT_TOTAL_RECONCILIATION_MISMATCH",
                severity="warning",
                message=(
                    "Computed statement total due does not match the extracted total due field "
                    f"(computed {reconciliation.computed_total_due:.2f}, statement {reconciliation.total_due:.2f}, difference {reconciliation.difference:.2f})."
                ),
            )
        )
    return findings


def _first_not_none(*values: float | None) -> float | None:
    return next((value for value in values if value is not None), None)


def _field_float(field: FinancialFieldCandidate) -> float | None:
    value = field.normalized_value or field.value_text
    try:
        return _parse_amount(value)
    except (TypeError, ValueError):
        return None


def _best_field_amount(fields: list[FinancialFieldCandidate], field_name: str) -> float | None:
    candidates = [field for field in fields if field.field_name == field_name and field.value_type == "amount" and _field_float(field) is not None]
    if not candidates:
        return None
    candidates.sort(key=_field_priority, reverse=True)
    return _field_float(candidates[0])


def _field_priority(field: FinancialFieldCandidate) -> tuple[int, float]:
    if "STATEMENT_SUMMARY_LABEL_DETECTED" in field.reason_codes:
        return (3, field.confidence)
    if "FIELD_LABEL_DETECTED" in field.reason_codes:
        return (2, field.confidence)
    return (1, field.confidence)


def _document_tables(
    request: TransactionExtractionRequest,
    document_type: str,
    transactions: list[TransactionCandidate],
    fields: list[FinancialFieldCandidate],
    entities: list[EntityCandidate],
    references: list[ReferenceCandidate],
    installments: list[InstallmentCandidate],
    reconciliation: ReconciliationResult,
    findings: list[ExtractionFinding],
) -> list[ExtractedTable]:
    tables: list[ExtractedTable] = []
    classification = request.classification
    document_rows = [
        {"Field": "Document type", "Value": document_type},
        {"Field": "Document subtype", "Value": classification.document_subtype if classification else "unknown"},
        {"Field": "Reconciliation", "Value": reconciliation.status},
        {"Field": "Transactions found", "Value": len(transactions)},
    ]
    tables.append(_table("document_summary", "Document Summary", ["Field", "Value"], document_rows))

    statement_rows = [
        {
            "Field": field.field_label or field.field_name.replace("_", " ").title(),
            "Value": field.normalized_value or field.value_text,
            "Currency": field.currency or "",
        }
        for field in fields
    ]
    if reconciliation.computed_total_due is not None and reconciliation.difference is not None:
        statement_rows.extend(
            [
                {"Field": "Computed total due", "Value": f"{reconciliation.computed_total_due:.2f}", "Currency": settings.default_currency},
                {"Field": "Difference", "Value": f"{reconciliation.difference:.2f}", "Currency": settings.default_currency},
            ]
        )
    tables.append(_table("statement_summary", "Statement Summary", ["Field", "Value", "Currency"], statement_rows))

    transaction_rows = [
        {
            "Transaction date": candidate.date_text or "",
            "Post date": candidate.posted_date_text or "",
            "Description": candidate.description,
            "Amount": f"{candidate.amount:.2f}",
            "Currency": candidate.currency,
            "Direction": candidate.direction,
            "Transaction type": candidate.transaction_type,
            "Spending category": candidate.spending_category,
            "Status": "Ready" if candidate.confidence >= settings.min_transaction_confidence else "Needs review",
        }
        for candidate in transactions
    ]
    tables.append(
        _table(
            "transactions",
            "Transactions",
            ["Transaction date", "Post date", "Description", "Amount", "Currency", "Direction", "Transaction type", "Spending category", "Status"],
            transaction_rows,
            transactions,
        )
    )

    entity_rows = [
        {"Type": entity.entity_type, "Value": entity.normalized_value or entity.value_text, "Confidence": f"{entity.confidence:.2f}"}
        for entity in entities
    ]
    entity_rows.extend(
        {"Type": reference.reference_type, "Value": reference.normalized_value or reference.value_text, "Confidence": f"{reference.confidence:.2f}"}
        for reference in references
    )
    tables.append(_table("entities_references", "Entities and References", ["Type", "Value", "Confidence"], entity_rows))

    installment_rows = [
        {
            "Purchase date": candidate.purchase_date_text or "",
            "Post date": candidate.posted_date_text or "",
            "Description": candidate.description,
            "Principal amount": f"{candidate.principal_amount:.2f}" if candidate.principal_amount is not None else "",
            "Current billed": f"{candidate.current_billing_amount:.2f}" if candidate.current_billing_amount is not None else "",
            "Remaining balance": f"{candidate.remaining_balance:.2f}" if candidate.remaining_balance is not None else "",
            "Currency": candidate.currency or "",
            "Term": candidate.term_text or "",
            "Status": "Ready" if candidate.confidence >= settings.min_transaction_confidence and candidate.term_text else "Needs review",
        }
        for candidate in installments
    ]
    tables.append(
        _table(
            "installments",
            "Installment Balances",
            ["Purchase date", "Post date", "Description", "Principal amount", "Current billed", "Remaining balance", "Currency", "Term", "Status"],
            installment_rows,
            installments,
        )
    )

    finding_rows = [{"Code": finding.code, "Severity": finding.severity, "Message": finding.message} for finding in findings]
    tables.append(_table("findings", "Findings", ["Code", "Severity", "Message"], finding_rows))
    return tables


def _table(
    table_id: str,
    title: str,
    columns: list[str],
    rows: list[dict[str, object]],
    sources: list[TransactionCandidate] | list[InstallmentCandidate] | None = None,
) -> ExtractedTable:
    return ExtractedTable(
        table_id=table_id,
        title=title,
        columns=columns,
        rows=[
            ExtractedTableRow(
                values=row,
                status=str(row.get("Status") or "extracted"),
                confidence=sources[index].confidence if sources and index < len(sources) else None,
                source=sources[index].source if sources and index < len(sources) else None,
            )
            for index, row in enumerate(rows)
        ],
    )
