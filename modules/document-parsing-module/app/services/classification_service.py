"""M5 - Document Parsing Module Start
Classifies parsed documents using shared vocabulary and rule signals.
M5/M6 End"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.parsing import ClassificationResult


FALLBACK_VOCABULARY = {
    "document_types": ["statement", "receipt", "invoice", "payment_proof", "utility_bill", "unknown"],
    "document_subtypes": {
        "statement": ["credit_card_statement", "account_statement", "loan_statement", "unknown"],
        "receipt": ["sales_receipt", "tax_receipt", "payment_terminal_receipt", "card_receipt", "medical_receipt", "unknown"],
        "invoice": ["service_invoice", "medical_invoice", "tax_invoice", "utility_invoice", "unknown"],
        "payment_proof": ["bank_transfer_proof", "card_payment_proof", "eftpos_proof", "unknown"],
        "utility_bill": ["electricity_bill", "water_bill", "gas_bill", "telecommunications_bill", "unknown"],
        "unknown": ["unknown"],
    },
}

FALLBACK_RULES = {
    "rules": [
        {
            "document_type": "statement",
            "document_subtype": "credit_card_statement",
            "reason_code": "CREDIT_CARD_STATEMENT_SIGNALS",
            "required_any": ["credit card", "card type", "mastercard", "visa"],
            "signals": [
                "statement of account",
                "credit limit",
                "minimum amount due",
                "payment due date",
                "finance charge",
                "previous balance",
                "unbilled installment",
                "total outstanding balance",
                "amount due",
            ],
            "minimum_score": 0.38,
        },
        {
            "document_type": "receipt",
            "document_subtype": "payment_terminal_receipt",
            "reason_code": "PAYMENT_TERMINAL_RECEIPT_SIGNALS",
            "required_any": ["eftpos", "terminal", "approved", "merchant copy", "rrn", "aid", "tvr", "tsi", "auth"],
            "signals": ["purchase", "rrn", "aid", "tvr", "tsi", "card", "auth", "merchant", "total"],
            "minimum_score": 0.34,
        },
        {
            "document_type": "receipt",
            "document_subtype": "tax_receipt",
            "reason_code": "RECEIPT_SIGNALS",
            "required_any": ["receipt", "tax invoice", "total", "subtotal", "gst", "eftpos", "purchase"],
            "signals": ["subtotal", "gst", "includes gst", "tax", "tax invoice", "eftpos", "purchase", "merchant", "total", "total due", "approved", "card"],
            "minimum_score": 0.35,
        },
        {
            "document_type": "invoice",
            "document_subtype": "medical_invoice",
            "reason_code": "MEDICAL_INVOICE_SIGNALS",
            "required_any": ["tax invoice no", "invoice", "nhi", "dob", "lab"],
            "signals": ["tests", "price", "price incl", "service fee", "payment history", "paid", "owing", "gst", "gender", "phone"],
            "minimum_score": 0.35,
        },
        {
            "document_type": "invoice",
            "document_subtype": "service_invoice",
            "reason_code": "INVOICE_SIGNALS",
            "required_any": ["invoice", "tax invoice", "bill to"],
            "signals": ["amount due", "invoice number", "invoice no", "payment terms", "due date", "subtotal", "gst", "paid", "owing"],
            "minimum_score": 0.35,
        },
        {
            "document_type": "payment_proof",
            "document_subtype": "bank_transfer_proof",
            "reason_code": "PAYMENT_PROOF_SIGNALS",
            "required_any": ["transfer successful", "confirmation no", "transfer amount"],
            "signals": ["transfer to", "transfer from", "confirmation", "reference", "payment", "sent via", "account"],
            "minimum_score": 0.35,
        },
        {
            "document_type": "utility_bill",
            "document_subtype": "unknown",
            "reason_code": "UTILITY_BILL_SIGNALS",
            "required_any": ["utility", "electricity", "water", "gas", "meter", "kwh"],
            "signals": ["usage", "charges", "billing period", "due date", "amount due", "service address"],
            "minimum_score": 0.35,
        },
    ]
}


def classify_document(
    *,
    text: str,
    supported_document_types: list[str],
    confidence_threshold: float,
    allow_unknown: bool,
) -> ClassificationResult:
    normalized_text = " ".join((text or "").lower().split())
    vocabulary = _load_vocabulary()
    rules = _load_rules()
    supported = {document_type.lower() for document_type in supported_document_types}
    allowed_types = {document_type.lower() for document_type in vocabulary.get("document_types", [])}
    allowed_subtypes = {
        document_type.lower(): {subtype.lower() for subtype in subtypes}
        for document_type, subtypes in vocabulary.get("document_subtypes", {}).items()
    }
    candidate_types = (supported & allowed_types) - {"unknown"}

    if not candidate_types:
        return ClassificationResult(
            document_type="unknown",
            document_subtype="unknown",
            confidence=0.0,
            status="unsupported",
            reason_codes=["NO_SUPPORTED_CLASSES"],
            scores={},
        )

    scored_rules = []
    scores: dict[str, float] = {}
    reason_codes: list[str] = []
    for rule in rules.get("rules", []):
        document_type = str(rule.get("document_type", "")).lower()
        document_subtype = str(rule.get("document_subtype", "unknown")).lower()
        if document_type not in candidate_types:
            continue
        if document_subtype not in allowed_subtypes.get(document_type, {"unknown"}):
            continue

        score, matched = _score_rule(normalized_text, rule)
        if score <= 0:
            continue
        key = f"{document_type}.{document_subtype}"
        scores[key] = round(score, 3)
        if score >= float(rule.get("minimum_score", 0.0)):
            reason_codes.append(str(rule.get("reason_code") or f"{document_type.upper()}_SIGNALS"))
        scored_rules.append((document_type, document_subtype, score, matched, rule))

    if not scored_rules:
        return _unknown_result(0.0, ["NO_CLASSIFICATION_SIGNALS"], allow_unknown)

    best_type, best_subtype, best_score, _matched, _rule = max(scored_rules, key=lambda item: item[2])
    confidence = round(best_score, 3)
    sorted_scores = sorted((item[2] for item in scored_rules), reverse=True)
    ambiguous = len(sorted_scores) > 1 and sorted_scores[0] > 0 and abs(sorted_scores[0] - sorted_scores[1]) < 0.10

    if confidence >= confidence_threshold and not ambiguous:
        return ClassificationResult(
            document_type=best_type,
            document_subtype=best_subtype,
            confidence=confidence,
            status="classified",
            reason_codes=sorted(set(reason_codes)),
            scores=scores,
        )

    receipt_override = _receipt_favored_result(scored_rules)
    if receipt_override:
        best_type, best_subtype, confidence = receipt_override
        return ClassificationResult(
            document_type=best_type,
            document_subtype=best_subtype,
            confidence=confidence,
            status="classified",
            reason_codes=sorted(set([*reason_codes, "RECEIPT_AMBIGUITY_RESOLVED"])),
            scores=scores,
        )

    if ambiguous:
        return ClassificationResult(
            document_type="unknown" if allow_unknown else best_type,
            document_subtype="unknown" if allow_unknown else best_subtype,
            confidence=confidence,
            status="ambiguous",
            reason_codes=sorted(set([*reason_codes, "AMBIGUOUS_DOCUMENT_SIGNALS"])),
            scores=scores,
        )

    return _unknown_result(
        confidence,
        [*reason_codes, "CONFIDENCE_BELOW_THRESHOLD", "POSSIBLE_NEW_DOCUMENT_SHAPE"],
        allow_unknown,
        best_type=best_type,
        best_subtype=best_subtype,
        scores=scores,
    )


def _score_rule(text: str, rule: dict[str, Any]) -> tuple[float, list[str]]:
    required_any = [str(value).lower() for value in rule.get("required_any", [])]
    signals = [str(value).lower() for value in rule.get("signals", [])]
    required_hits = [signal for signal in required_any if _contains_signal(text, signal)]
    signal_hits = [signal for signal in signals if _contains_signal(text, signal)]
    if required_any and not required_hits:
        return 0.0, []
    if not signal_hits and not required_hits:
        return 0.0, []
    required_score = 0.35 if required_hits else 0.0
    signal_score = 0.65 * (len(signal_hits) / max(1, len(signals)))
    return min(1.0, required_score + signal_score), [*required_hits, *signal_hits]


def _contains_signal(text: str, signal: str) -> bool:
    escaped = re_escape(signal)
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _receipt_favored_result(scored_rules: list[tuple[str, str, float, list[str], dict[str, Any]]]) -> tuple[str, str, float] | None:
    receipt_candidates = [
        (document_type, document_subtype, score, matched, rule)
        for document_type, document_subtype, score, matched, rule in scored_rules
        if document_type == "receipt"
    ]
    if not receipt_candidates:
        return None
    best_type, best_subtype, best_score, _matched, rule = max(receipt_candidates, key=lambda item: item[2])
    combined_matches = {match for *_prefix, matches, _rule in receipt_candidates for match in matches}
    receipt_evidence = {
        "receipt",
        "tax invoice",
        "total",
        "subtotal",
        "gst",
        "eftpos",
        "purchase",
        "approved",
        "card",
        "terminal",
    }
    if best_score >= float(rule.get("minimum_score", 0.0)) and len(receipt_evidence & combined_matches) >= 3:
        return best_type, best_subtype, round(best_score, 3)
    return None


def re_escape(value: str) -> str:
    return re.escape(" ".join(value.split()))


def _unknown_result(
    confidence: float,
    reason_codes: list[str],
    allow_unknown: bool,
    best_type: str = "unknown",
    best_subtype: str = "unknown",
    scores: dict[str, float] | None = None,
) -> ClassificationResult:
    return ClassificationResult(
        document_type="unknown" if allow_unknown else best_type,
        document_subtype="unknown" if allow_unknown else best_subtype,
        confidence=round(confidence, 3),
        status="unknown",
        reason_codes=sorted(set(reason_codes)),
        scores=scores or {},
    )


@lru_cache(maxsize=1)
def _load_vocabulary() -> dict[str, Any]:
    return _load_json_file(settings.document_classification_vocabulary_path, FALLBACK_VOCABULARY)


@lru_cache(maxsize=1)
def _load_rules() -> dict[str, Any]:
    return _load_json_file(settings.document_classification_rules_path, FALLBACK_RULES)


def _load_json_file(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
