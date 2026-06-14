"""M7 - Transaction Extraction Module Start
Provides optional AI-assisted transaction classification fallback.
M7 End"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from app.config import settings
from app.models.extraction import TransactionCandidate


SENSITIVE_PATTERN = re.compile(r"\b\d{6,}\b")
AI_SKIP_DISABLED = "AI_SKIPPED_DISABLED"
AI_SKIP_UNSUPPORTED_PROVIDER = "AI_SKIPPED_UNSUPPORTED_PROVIDER"
AI_SKIP_MODEL_MISSING = "AI_SKIPPED_MODEL_MISSING"
AI_SKIP_API_KEY_MISSING = "AI_SKIPPED_API_KEY_MISSING"
AI_SKIP_ENDPOINT_MISSING = "AI_SKIPPED_ENDPOINT_MISSING"
AI_SKIP_PROVIDER_CALL_FAILED = "AI_SKIPPED_PROVIDER_CALL_FAILED"
AI_SKIP_RESPONSE_PARSE_FAILED = "AI_SKIPPED_RESPONSE_PARSE_FAILED"


def should_try_ai_classification(transaction_result: dict[str, object], category_result: dict[str, object]) -> bool:
    return _weak_result(transaction_result) or _weak_result(category_result)


def ai_skip_reason() -> str | None:
    if not settings.transaction_classification_ai_enabled:
        return AI_SKIP_DISABLED
    if settings.transaction_classification_ai_provider not in {"gemini", "openai", "openai_compatible"}:
        return AI_SKIP_UNSUPPORTED_PROVIDER
    if not settings.transaction_classification_ai_model:
        return AI_SKIP_MODEL_MISSING
    if not os.getenv(settings.transaction_classification_ai_api_key_env):
        return AI_SKIP_API_KEY_MISSING
    if not _request_endpoint():
        return AI_SKIP_ENDPOINT_MISSING
    return None


def ai_classify_transaction(
    *,
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    transaction_result: dict[str, object],
    category_result: dict[str, object],
    active_recognition_context: dict[str, Any] | None = None,
) -> dict[str, object] | None:
    skip_reason = ai_skip_reason()
    if skip_reason:
        return None
    api_key = os.getenv(settings.transaction_classification_ai_api_key_env) or ""

    payload = _request_payload(
        candidate=candidate,
        document_type=document_type,
        document_subtype=document_subtype,
        transaction_result=transaction_result,
        category_result=category_result,
        active_recognition_context=active_recognition_context or {},
    )
    endpoint = _request_endpoint()

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=_request_headers(api_key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_response = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError, TimeoutError):
        return None

    try:
        return _parse_ai_response(raw_response)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def merge_rule_and_ai_classification(
    *,
    candidate: TransactionCandidate,
    rule_transaction: dict[str, object],
    rule_category: dict[str, object],
    ai_result: dict[str, object] | None,
) -> dict[str, object]:
    base = {
        "transaction": rule_transaction,
        "category": rule_category,
        "classification_source": _rule_source(rule_transaction, rule_category),
        "ai_model_name": None,
        "ai_model_version": None,
        "ai_confidence": None,
        "classification_review_required": False,
        "classification_review_reason_codes": [],
    }
    if ai_result is None:
        return base

    ai_confidence = _confidence(ai_result.get("confidence"))
    ai_model_name = str(ai_result.get("ai_model_name") or settings.transaction_classification_ai_model)
    ai_model_version = str(
        ai_result.get("ai_model_version")
        or settings.transaction_classification_ai_model_version
        or settings.transaction_classification_ai_model
    )
    if ai_confidence < settings.transaction_classification_ai_min_confidence:
        return {
            **base,
            "classification_source": "rules_ai_low_confidence",
            "ai_model_name": ai_model_name,
            "ai_model_version": ai_model_version,
            "ai_confidence": ai_confidence,
            "classification_review_required": True,
            "classification_review_reason_codes": ["AI_CONFIDENCE_BELOW_THRESHOLD"],
        }

    ai_transaction = _ai_transaction_result(ai_result)
    ai_category = _ai_category_result(ai_result)
    rule_transaction_label = str(rule_transaction.get("label") or "unknown")
    rule_category_label = str(rule_category.get("label") or "uncategorized")
    conflicts = []
    if rule_transaction.get("status") == "classified" and rule_transaction_label != ai_transaction["label"]:
        conflicts.append("RULE_AI_TRANSACTION_TYPE_CONFLICT")
    if rule_category.get("status") == "classified" and rule_category_label != ai_category["label"]:
        conflicts.append("RULE_AI_SPENDING_CATEGORY_CONFLICT")
    if conflicts:
        return {
            **base,
            "classification_source": "rules_ai_conflict",
            "ai_model_name": ai_model_name,
            "ai_model_version": ai_model_version,
            "ai_confidence": ai_confidence,
            "classification_review_required": True,
            "classification_review_reason_codes": conflicts,
        }

    source = "rules_ai_agreement" if _strong_result(rule_transaction) and _strong_result(rule_category) else "ai_assist"
    return {
        "transaction": _merge_scores(ai_transaction, rule_transaction),
        "category": _merge_scores(ai_category, rule_category),
        "classification_source": source,
        "ai_model_name": ai_model_name,
        "ai_model_version": ai_model_version,
        "ai_confidence": ai_confidence,
        "classification_review_required": bool(ai_result.get("requires_review")),
        "classification_review_reason_codes": [str(code) for code in ai_result.get("review_reason_codes") or []],
    }


def _weak_result(result: dict[str, object]) -> bool:
    return (
        result.get("status") in {"unknown", "ambiguous"}
        or _confidence(result.get("confidence")) < settings.transaction_classification_ai_trigger_threshold
    )


def _strong_result(result: dict[str, object]) -> bool:
    return result.get("status") == "classified" and _confidence(result.get("confidence")) >= settings.transaction_classification_ai_trigger_threshold


def _rule_source(transaction_result: dict[str, object], category_result: dict[str, object]) -> str:
    if transaction_result.get("status") == "unknown" and category_result.get("status") == "unknown":
        return "unknown"
    return "rules"


def _request_payload(
    *,
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    transaction_result: dict[str, object],
    category_result: dict[str, object],
    active_recognition_context: dict[str, Any],
) -> dict[str, Any]:
    system_prompt = (
        "Classify one financial transaction for the Stats app. Return only compact JSON "
        "with transaction_type, transaction_subtype, spending_category, spending_subcategory, "
        "confidence, reason_codes, explanation, requires_review, transaction_vocabulary_status, "
        "and spending_vocabulary_status. Prefer active_recognition_context labels when they fit. "
        "Propose a new transaction or spending label only when no active label fits."
    )
    user_prompt = {
        "document_type": document_type,
        "document_subtype": document_subtype,
        "active_recognition_context": active_recognition_context,
        "rule_transaction_result": transaction_result,
        "rule_spending_category_result": category_result,
        "candidate": {
            "description": _redact(candidate.description),
            "amount": candidate.amount,
            "currency": candidate.currency,
            "direction": candidate.direction,
            "source_text": _redact(candidate.source.text),
            "reason_codes": candidate.reason_codes,
        },
    }
    encoded_user_prompt = _encode_limited_user_prompt(user_prompt, settings.transaction_classification_ai_max_chars)

    if settings.transaction_classification_ai_provider == "gemini":
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": encoded_user_prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

    return {
        "model": settings.transaction_classification_ai_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": encoded_user_prompt},
        ],
    }


def _encode_limited_user_prompt(user_prompt: dict[str, Any], max_chars: int) -> str:
    encoded = _json_prompt(user_prompt)
    if max_chars <= 0 or len(encoded) <= max_chars:
        return encoded

    prompt = dict(user_prompt)
    candidate = dict(prompt.get("candidate") or {})
    source_text = str(candidate.get("source_text") or "")
    if not source_text:
        return encoded

    low = 0
    high = len(source_text)
    best = ""
    while low <= high:
        midpoint = (low + high) // 2
        candidate["source_text"] = source_text[:midpoint]
        prompt["candidate"] = candidate
        trial = _json_prompt(prompt)
        if len(trial) <= max_chars:
            best = trial
            low = midpoint + 1
        else:
            high = midpoint - 1
    if best:
        return best

    candidate["source_text"] = ""
    prompt["candidate"] = candidate
    encoded_without_source = _json_prompt(prompt)
    if len(encoded_without_source) <= max_chars:
        return encoded_without_source

    return _minimal_prompt(user_prompt, max_chars)


def _json_prompt(prompt: dict[str, Any]) -> str:
    return json.dumps(prompt, ensure_ascii=True, separators=(",", ":"))


def _minimal_prompt(user_prompt: dict[str, Any], max_chars: int) -> str:
    candidate = dict(user_prompt.get("candidate") or {})
    minimal = {
        "document_type": user_prompt.get("document_type"),
        "document_subtype": user_prompt.get("document_subtype"),
        "active_recognition_context": _minimal_recognition_context(user_prompt.get("active_recognition_context")),
        "candidate": {
            "description": str(candidate.get("description") or ""),
            "amount": candidate.get("amount"),
            "currency": candidate.get("currency"),
            "direction": candidate.get("direction"),
            "source_text": "",
            "reason_codes": [],
        },
    }
    encoded = _json_prompt(minimal)
    if len(encoded) <= max_chars:
        return encoded

    description = minimal["candidate"]["description"]
    low = 0
    high = len(description)
    best = _json_prompt({"candidate": {"source_text": ""}})
    while low <= high:
        midpoint = (low + high) // 2
        minimal["candidate"]["description"] = description[:midpoint]
        trial = _json_prompt(minimal)
        if len(trial) <= max_chars:
            best = trial
            low = midpoint + 1
        else:
            high = midpoint - 1
    if len(best) <= max_chars:
        return best
    return "{}"


def _minimal_recognition_context(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    context: dict[str, Any] = {}
    if value.get("version"):
        context["version"] = value.get("version")
    for scope in ["transaction", "spending"]:
        scoped = value.get(scope)
        if isinstance(scoped, dict):
            context[scope] = {"vocabulary": scoped.get("vocabulary", {})}
    return context


def _request_headers(api_key: str) -> dict[str, str]:
    if settings.transaction_classification_ai_provider == "gemini":
        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _request_endpoint() -> str:
    if settings.transaction_classification_ai_endpoint:
        return settings.transaction_classification_ai_endpoint
    if settings.transaction_classification_ai_provider == "gemini":
        model_name = settings.transaction_classification_ai_model.strip()
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    return ""


def _parse_ai_response(raw_response: str) -> dict[str, object] | None:
    payload = json.loads(raw_response)
    content = None
    if isinstance(payload, dict):
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            content = message.get("content") if isinstance(message, dict) else None
        content = content or payload.get("output_text")
        if content is None:
            content = _gemini_response_text(payload)
    if not isinstance(content, str):
        return None

    parsed = _extract_json_object(content)
    if not parsed:
        return None

    confidence = _confidence(parsed.get("confidence"))
    return {
        "transaction_type": _clean_label(parsed.get("transaction_type"), "unknown"),
        "transaction_subtype": _clean_label(parsed.get("transaction_subtype"), "unknown"),
        "spending_category": _clean_label(parsed.get("spending_category"), "uncategorized"),
        "spending_subcategory": _clean_label(parsed.get("spending_subcategory"), "unknown"),
        "confidence": confidence,
        "reason_codes": _reason_codes(parsed.get("reason_codes")),
        "requires_review": bool(parsed.get("requires_review", confidence < settings.transaction_classification_ai_min_confidence)),
        "review_reason_codes": _reason_codes(parsed.get("review_reason_codes")),
        "ai_model_name": settings.transaction_classification_ai_model,
        "ai_model_version": settings.transaction_classification_ai_model_version or settings.transaction_classification_ai_model,
        "transaction_vocabulary_status": _clean_status(parsed.get("transaction_vocabulary_status")),
        "spending_vocabulary_status": _clean_status(parsed.get("spending_vocabulary_status")),
    }


def _ai_transaction_result(ai_result: dict[str, object]) -> dict[str, object]:
    confidence = _confidence(ai_result.get("confidence"))
    transaction_type = str(ai_result.get("transaction_type") or "unknown")
    transaction_subtype = str(ai_result.get("transaction_subtype") or "unknown")
    return {
        "label": transaction_type,
        "subtype": transaction_subtype,
        "confidence": confidence,
        "status": "classified" if confidence >= settings.transaction_classification_ai_min_confidence else "ambiguous",
        "reason_codes": sorted(set([*list(ai_result.get("reason_codes") or []), "AI_ASSISTED_TRANSACTION_CLASSIFICATION"])),
        "scores": {f"ai.transaction.{transaction_type}.{transaction_subtype}": confidence},
    }


def _ai_category_result(ai_result: dict[str, object]) -> dict[str, object]:
    confidence = _confidence(ai_result.get("confidence"))
    category = str(ai_result.get("spending_category") or "uncategorized")
    subcategory = str(ai_result.get("spending_subcategory") or "unknown")
    return {
        "label": category,
        "subtype": subcategory,
        "confidence": confidence,
        "status": "classified" if confidence >= settings.transaction_classification_ai_min_confidence else "ambiguous",
        "reason_codes": sorted(set([*list(ai_result.get("reason_codes") or []), "AI_ASSISTED_SPENDING_CATEGORY_CLASSIFICATION"])),
        "scores": {f"ai.category.{category}.{subcategory}": confidence},
    }


def _merge_scores(ai_result: dict[str, object], rule_result: dict[str, object]) -> dict[str, object]:
    return {
        **ai_result,
        "scores": {**dict(rule_result.get("scores") or {}), **dict(ai_result.get("scores") or {})},
    }


def _gemini_response_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    candidate = candidates[0]
    if not isinstance(candidate, dict):
        return None
    content = candidate.get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    texts = [part.get("text") for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
    return "\n".join(texts) if texts else None


def _extract_json_object(content: str) -> dict[str, Any] | None:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            return None
        parsed = json.loads(stripped[start : end + 1])
    return parsed if isinstance(parsed, dict) else None


def _redact(text: str) -> str:
    return SENSITIVE_PATTERN.sub(lambda match: f"***{match.group(0)[-4:]}", text or "")


def _confidence(value: object) -> float:
    try:
        return round(max(0.0, min(float(value), 1.0)), 3)
    except (TypeError, ValueError):
        return 0.0


def _clean_label(value: object, default: str) -> str:
    text = str(value or default).strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", text) or default


def _clean_status(value: object) -> str:
    text = str(value or "unknown").strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]+", "", text) or "unknown"


def _reason_codes(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(code).strip().upper() for code in value if str(code).strip()]
