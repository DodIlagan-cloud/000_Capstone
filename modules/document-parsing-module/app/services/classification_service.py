"""M5 - Document Parsing Module Start
Classifies parsed documents using shared vocabulary and rule signals.
M5/M6 End"""

import json
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.models.parsing import ClassificationResult
from app.services.ai_classification_service import (
    ai_classify_document,
    merge_rule_and_ai_classification,
    should_try_ai_classification,
)


_active_settings_cache: tuple[float, dict[str, Any]] | None = None


def classify_document(
    *,
    text: str,
    supported_document_types: list[str],
    confidence_threshold: float,
    allow_unknown: bool,
) -> ClassificationResult:
    normalized_text = " ".join((text or "").lower().split())
    active_settings = _load_active_settings()
    if not active_settings:
        return ClassificationResult(
            document_type="unknown",
            document_subtype="unknown",
            confidence=0.0,
            status="unknown",
            reason_codes=["RECOGNITION_SETTINGS_UNAVAILABLE"],
            scores={},
            requires_review=True,
            review_reason_codes=["RECOGNITION_SETTINGS_UNAVAILABLE"],
            classification_vocabulary_status="settings_unavailable",
        )

    vocabulary = active_settings.get("document_vocabulary", {})
    rules = active_settings.get("document_rules", {})
    supported = {document_type.lower() for document_type in supported_document_types}
    allowed_types = {document_type.lower() for document_type in vocabulary.get("document_types", [])}
    allowed_subtypes = {
        document_type.lower(): {subtype.lower() for subtype in subtypes}
        for document_type, subtypes in vocabulary.get("document_subtypes", {}).items()
    }
    candidate_types = (supported & allowed_types) - {"unknown"}

    if not candidate_types:
        return _finalize_classification(
            ClassificationResult(
                document_type="unknown",
                document_subtype="unknown",
                confidence=0.0,
                status="unsupported",
                reason_codes=["NO_SUPPORTED_CLASSES"],
                scores={},
            ),
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
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
        unknown = _unknown_result(0.0, ["NO_CLASSIFICATION_SIGNALS"], allow_unknown)
        unknown = _content_shape_suggestion(
            unknown,
            text=normalized_text,
            supported_document_types=supported,
            approved_document_types=allowed_types,
        )
        return _finalize_classification(
            unknown,
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
        )

    best_type, best_subtype, best_score, _matched, _rule = max(scored_rules, key=lambda item: item[2])
    confidence = round(best_score, 3)
    sorted_scores = sorted((item[2] for item in scored_rules), reverse=True)
    ambiguous = len(sorted_scores) > 1 and sorted_scores[0] > 0 and abs(sorted_scores[0] - sorted_scores[1]) < 0.10

    if confidence >= confidence_threshold and not ambiguous:
        return _finalize_classification(
            ClassificationResult(
                document_type=best_type,
                document_subtype=best_subtype,
                confidence=confidence,
                status="classified",
                reason_codes=sorted(set(reason_codes)),
                scores=scores,
            ),
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
        )

    if best_type == "statement" and confidence >= confidence_threshold:
        return _finalize_classification(
            ClassificationResult(
                document_type=best_type,
                document_subtype=best_subtype,
                confidence=confidence,
                status="classified",
                reason_codes=sorted(set([*reason_codes, "STATEMENT_AMBIGUITY_RESOLVED"])),
                scores=scores,
            ),
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
        )

    receipt_override = _receipt_favored_result(scored_rules)
    if receipt_override:
        best_type, best_subtype, confidence = receipt_override
        return _finalize_classification(
            ClassificationResult(
                document_type=best_type,
                document_subtype=best_subtype,
                confidence=confidence,
                status="classified",
                reason_codes=sorted(set([*reason_codes, "RECEIPT_AMBIGUITY_RESOLVED"])),
                scores=scores,
            ),
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
        )

    if ambiguous:
        ambiguous_result = ClassificationResult(
            document_type="unknown" if allow_unknown else best_type,
            document_subtype="unknown" if allow_unknown else best_subtype,
            confidence=confidence,
            status="ambiguous",
            reason_codes=sorted(set([*reason_codes, "AMBIGUOUS_DOCUMENT_SIGNALS"])),
            scores=scores,
        )
        ambiguous_result = _content_shape_suggestion(
            ambiguous_result,
            text=normalized_text,
            supported_document_types=supported,
            approved_document_types=allowed_types,
        )
        return _finalize_classification(
            ambiguous_result,
            text=text,
            supported_document_types=supported_document_types,
            approved_document_types=allowed_types,
            active_settings=active_settings,
        )

    unknown = _unknown_result(
        confidence,
        [*reason_codes, "CONFIDENCE_BELOW_THRESHOLD", "POSSIBLE_NEW_DOCUMENT_SHAPE"],
        allow_unknown,
        best_type=best_type,
        best_subtype=best_subtype,
        scores=scores,
    )
    unknown = _content_shape_suggestion(
        unknown,
        text=normalized_text,
        supported_document_types=supported,
        approved_document_types=allowed_types,
    )
    return _finalize_classification(
        unknown,
        text=text,
        supported_document_types=supported_document_types,
        approved_document_types=allowed_types,
        active_settings=active_settings,
    )


def _finalize_classification(
    rule_result: ClassificationResult,
    *,
    text: str,
    supported_document_types: list[str],
    approved_document_types: set[str],
    active_settings: dict[str, Any] | None = None,
) -> ClassificationResult:
    context_version = _recognition_context_version(active_settings)
    rule_result = _with_context_metadata(rule_result, context_version=context_version)
    if not settings.classification_ai_enabled or not should_try_ai_classification(rule_result):
        return rule_result

    ai_result = ai_classify_document(
        text=text,
        supported_document_types=supported_document_types,
        rule_result=rule_result,
        active_recognition_context=_document_ai_context(active_settings),
    )
    return merge_rule_and_ai_classification(
        rule_result=rule_result,
        ai_result=ai_result,
        approved_document_types=approved_document_types,
        recognition_context_version=context_version,
    )


def _with_context_metadata(result: ClassificationResult, *, context_version: str | None) -> ClassificationResult:
    return result.model_copy(
        update={
            "classification_vocabulary_status": "active_vocabulary_match"
            if result.document_type not in {"unknown", ""}
            else "unknown_or_unclassified",
            "recognition_context_version": context_version,
        }
    )


def _recognition_context_version(active_settings: dict[str, Any] | None) -> str | None:
    if not active_settings:
        return None
    context = active_settings.get("recognition_context")
    if isinstance(context, dict) and context.get("version"):
        return str(context["version"])
    if active_settings.get("recognition_context_version"):
        return str(active_settings["recognition_context_version"])
    return None


def _document_ai_context(active_settings: dict[str, Any] | None) -> dict[str, Any]:
    if not active_settings:
        return {}
    context = active_settings.get("recognition_context")
    if isinstance(context, dict) and isinstance(context.get("document"), dict):
        return {
            "version": context.get("version") or active_settings.get("recognition_context_version"),
            "document": context["document"],
        }
    return {
        "version": _recognition_context_version(active_settings),
        "document": {
            "vocabulary": active_settings.get("document_vocabulary", {}),
            "rules": active_settings.get("document_rules", {}),
        },
    }


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
    tokens = _signal_tokens(signal)
    if not tokens:
        return False
    escaped = [re.escape(token) for token in tokens]
    pattern = r"[^a-z0-9]+".join(escaped)
    return bool(re.search(rf"(?<![a-z0-9]){pattern}(?![a-z0-9])", text))


def _signal_tokens(signal: str) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", signal.lower().replace("_", " ")) if token]


def _receipt_favored_result(scored_rules: list[tuple[str, str, float, list[str], dict[str, Any]]]) -> tuple[str, str, float] | None:
    # Receipts often share invoice/payment vocabulary; prefer receipt only when
    # multiple receipt-specific signals are present, not on a single weak tie.
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


def _content_shape_suggestion(
    result: ClassificationResult,
    *,
    text: str,
    supported_document_types: set[str],
    approved_document_types: set[str],
) -> ClassificationResult:
    if result.suggested_document_type or "receipt" not in supported_document_types or "receipt" in approved_document_types:
        return result

    receipt_signals = {
        "receipt",
        "tax invoice",
        "customer receipt",
        "merchant copy",
        "sales",
        "items",
        "total",
        "tax",
        "gst",
        "eftpos",
        "purchase",
        "approved",
        "terminal",
        "bank card",
        "debit",
        "card",
        "rrn",
        "auth",
    }
    hits = sorted(signal for signal in receipt_signals if _contains_signal(text, signal))
    has_amount = bool(re.search(r"(?:\$|nzd|total|eftpos|purchase)\s*[:=]?\s*\$?\s*\d+[., ]\d{2}", text))
    strong_anchor = bool({"receipt", "tax invoice", "customer receipt", "total"} & set(hits))
    payment_anchor = bool({"eftpos", "approved", "terminal", "bank card", "debit", "card", "rrn", "auth"} & set(hits))
    commerce_anchor = bool({"sales", "items", "purchase"} & set(hits))
    if len(hits) < 3 or not has_amount or not strong_anchor or not (payment_anchor or commerce_anchor):
        return result

    terminal_hits = {"eftpos", "approved", "terminal", "bank card", "debit", "card", "rrn", "auth", "merchant copy"} & set(hits)
    subtype = "payment_terminal_receipt" if len(terminal_hits) >= 2 else "sales_receipt"
    confidence = round(min(0.9, 0.48 + (0.05 * len(hits))), 3)
    reason_codes = sorted(
        set(
            [
                *result.reason_codes,
                "PENDING_DOCUMENT_LABEL_SUGGESTION",
                "CONTENT_RECEIPT_SHAPE_SUGGESTION",
                *[f"RECEIPT_SIGNAL_{signal.upper().replace(' ', '_')}" for signal in hits[:8]],
            ]
        )
    )
    return result.model_copy(
        update={
            "confidence": max(result.confidence, confidence),
            "requires_review": True,
            "review_reason_codes": sorted(
                set([*result.review_reason_codes, "PENDING_DOCUMENT_LABEL_SUGGESTION"])
            ),
            "reason_codes": reason_codes,
            "recognition_suggestion_status": "pending",
            "suggested_document_type": "receipt",
            "suggested_document_subtype": subtype,
            "suggestion_confidence": confidence,
            "suggestion_reason_codes": reason_codes,
            "suggestion_source": "m5_rules_document_shape",
            "suggestion_evidence_ref": "m5:redacted_document_shape_signals",
        }
    )


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


def _load_active_settings() -> dict[str, Any] | None:
    global _active_settings_cache
    if not settings.recognition_settings_url:
        return None
    now = time.monotonic()
    if _active_settings_cache and now - _active_settings_cache[0] < settings.recognition_settings_cache_seconds:
        return _active_settings_cache[1]
    try:
        request = Request(settings.recognition_settings_url)
        if settings.recognition_settings_internal_key:
            request.add_header("X-Stats-Internal-Key", settings.recognition_settings_internal_key)
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, HTTPError, URLError, json.JSONDecodeError):
        if _active_settings_cache:
            return _active_settings_cache[1]
        return None
    _active_settings_cache = (now, payload)
    return payload


def _load_vocabulary() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("document_vocabulary"), dict):
        return active["document_vocabulary"]
    return {}


def _load_rules() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("document_rules"), dict):
        return active["document_rules"]
    return {"rules": []}


def _clear_settings_cache() -> None:
    global _active_settings_cache
    _active_settings_cache = None


_load_vocabulary.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
_load_rules.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
