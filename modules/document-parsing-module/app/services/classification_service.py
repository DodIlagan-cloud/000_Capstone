"""M5 - Document Parsing Module Start
Classifies parsed documents using transparent keyword signals.
M5/M6 End"""

from app.models.parsing import ClassificationResult


KEYWORDS: dict[str, list[str]] = {
    "bank_statement": [
        "bank statement",
        "account balance",
        "closing balance",
        "opening balance",
        "transaction",
        "debit",
        "credit",
    ],
    "receipt": ["receipt", "subtotal", "gst", "tax invoice", "eftpos", "merchant", "total"],
    "invoice": ["invoice", "amount due", "invoice number", "bill to", "due date", "payment terms"],
    "utility_bill": ["utility", "electricity", "water", "gas", "usage", "meter", "kwh", "charges"],
}


def classify_document(
    *,
    text: str,
    supported_document_types: list[str],
    confidence_threshold: float,
    allow_unknown: bool,
) -> ClassificationResult:
    normalized_text = (text or "").lower()
    supported = {document_type.lower() for document_type in supported_document_types}
    scores: dict[str, float] = {}
    reason_codes: list[str] = []

    for document_type, keywords in KEYWORDS.items():
        if document_type not in supported:
            continue

        hits = sum(1 for keyword in keywords if keyword in normalized_text)
        if hits:
            reason_codes.append(f"{document_type.upper()}_SIGNALS")
        scores[document_type] = hits / max(1, len(keywords))

    if not scores:
        return ClassificationResult(
            document_type="unknown",
            confidence=0.0,
            status="unsupported",
            reason_codes=["NO_SUPPORTED_CLASSES"],
            scores={},
        )

    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    confidence = round(best_score, 3)
    top_scores = sorted(scores.values(), reverse=True)
    ambiguous = len(top_scores) > 1 and top_scores[0] > 0 and abs(top_scores[0] - top_scores[1]) < 0.10

    if confidence >= confidence_threshold and not ambiguous:
        return ClassificationResult(
            document_type=best_type,
            confidence=confidence,
            status="classified",
            reason_codes=reason_codes,
            scores={key: round(value, 3) for key, value in scores.items()},
        )

    if ambiguous:
        status = "ambiguous"
        reason_codes = [*reason_codes, "AMBIGUOUS_DOCUMENT_SIGNALS"]
    else:
        status = "unknown"
        reason_codes = [*reason_codes, "CONFIDENCE_BELOW_THRESHOLD"]

    return ClassificationResult(
        document_type="unknown" if allow_unknown else best_type,
        confidence=confidence,
        status=status,
        reason_codes=reason_codes,
        scores={key: round(value, 3) for key, value in scores.items()},
    )
