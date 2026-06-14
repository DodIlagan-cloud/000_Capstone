"""M5 - Document Parsing Module Start
Provides optional AI-assisted document classification fallback.
M5/M6 End"""

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from app.config import settings
from app.models.parsing import ClassificationResult
from app.services.redaction_service import redact_text


def ai_classify_document(
    *,
    text: str,
    supported_document_types: list[str],
    rule_result: ClassificationResult,
    active_recognition_context: dict[str, Any] | None = None,
) -> ClassificationResult | None:
    if not settings.classification_ai_enabled:
        return None
    if settings.classification_ai_provider not in {"gemini", "openai", "openai_compatible"}:
        return None
    if not settings.classification_ai_model:
        return None

    api_key = os.getenv(settings.classification_ai_api_key_env)
    if not api_key:
        return None

    redacted_text, _counts = redact_text(text, settings.classification_ai_max_chars)
    payload = _request_payload(redacted_text, supported_document_types, rule_result, active_recognition_context or {})
    headers = _request_headers(api_key)
    endpoint = _request_endpoint()
    if not endpoint:
        return None

    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_response = response.read().decode("utf-8")
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    try:
        return _parse_ai_response(raw_response, supported_document_types)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def should_try_ai_classification(rule_result: ClassificationResult) -> bool:
    return (
        rule_result.status in {"unknown", "ambiguous"}
        or rule_result.confidence < settings.classification_ai_trigger_threshold
        or "POSSIBLE_NEW_DOCUMENT_SHAPE" in rule_result.reason_codes
    )


def merge_rule_and_ai_classification(
    *,
    rule_result: ClassificationResult,
    ai_result: ClassificationResult | None,
    approved_document_types: set[str],
    recognition_context_version: str | None = None,
) -> ClassificationResult:
    if ai_result is None:
        return rule_result

    if ai_result.confidence < settings.classification_ai_min_confidence:
        return rule_result.model_copy(
            update={
                "classification_source": "rules_ai_low_confidence",
                "ai_model_name": ai_result.ai_model_name,
                "ai_model_version": ai_result.ai_model_version,
                "ai_confidence": ai_result.confidence,
                "requires_review": True,
                "review_reason_codes": sorted(set([*rule_result.review_reason_codes, "AI_CONFIDENCE_BELOW_THRESHOLD"])),
                "reason_codes": sorted(set([*rule_result.reason_codes, "AI_ASSIST_LOW_CONFIDENCE"])),
                "recognition_context_version": recognition_context_version or rule_result.recognition_context_version,
            }
        )

    if rule_result.status == "classified" and rule_result.document_type != ai_result.document_type:
        return rule_result.model_copy(
            update={
                "classification_source": "rules_ai_conflict",
                "ai_model_name": ai_result.ai_model_name,
                "ai_model_version": ai_result.ai_model_version,
                "ai_confidence": ai_result.confidence,
                "requires_review": True,
                "review_reason_codes": sorted(set([*rule_result.review_reason_codes, "RULE_AI_CLASSIFICATION_CONFLICT"])),
                "reason_codes": sorted(set([*rule_result.reason_codes, "AI_ASSIST_CONFLICT"])),
                "recognition_context_version": recognition_context_version or rule_result.recognition_context_version,
            }
        )

    if ai_result.document_type not in approved_document_types:
        suggested_document_type = rule_result.suggested_document_type or ai_result.document_type
        suggested_document_subtype = rule_result.suggested_document_subtype or ai_result.document_subtype
        suggestion_confidence = rule_result.suggestion_confidence or ai_result.confidence
        suggestion_reason_codes = rule_result.suggestion_reason_codes or ai_result.reason_codes
        suggestion_source = rule_result.suggestion_source or "m5_ai_document_classification"
        suggestion_evidence_ref = rule_result.suggestion_evidence_ref or "m5:redacted_classification_prompt"
        return rule_result.model_copy(
            update={
                "document_type": "unknown",
                "document_subtype": "unknown",
                "confidence": max(rule_result.confidence, ai_result.confidence),
                "status": "unknown",
                "classification_source": "ai_suggested_document_label",
                "ai_model_name": ai_result.ai_model_name,
                "ai_model_version": ai_result.ai_model_version,
                "ai_confidence": ai_result.confidence,
                "requires_review": True,
                "review_reason_codes": sorted(
                    set([*rule_result.review_reason_codes, "PENDING_DOCUMENT_LABEL_SUGGESTION"])
                ),
                "reason_codes": sorted(set([*rule_result.reason_codes, "AI_SUGGESTED_INACTIVE_DOCUMENT_LABEL"])),
                "recognition_suggestion_id": None,
                "recognition_suggestion_status": "pending",
                "suggested_document_type": suggested_document_type,
                "suggested_document_subtype": suggested_document_subtype,
                "suggestion_confidence": suggestion_confidence,
                "suggestion_reason_codes": sorted(set([*suggestion_reason_codes, "PENDING_DOCUMENT_LABEL_SUGGESTION"])),
                "suggestion_source": suggestion_source,
                "suggestion_evidence_ref": suggestion_evidence_ref,
                "classification_vocabulary_status": "outside_vocabulary_proposal",
                "recognition_context_version": recognition_context_version or rule_result.recognition_context_version,
                "classification_confirmation_mode": "upload_review_save",
            }
        )

    source = "rules_ai_agreement" if rule_result.status == "classified" else "ai_assist"
    return ai_result.model_copy(
        update={
            "classification_source": source,
            "reason_codes": sorted(set([*ai_result.reason_codes, "AI_ASSISTED_CLASSIFICATION"])),
            "scores": {**rule_result.scores, **ai_result.scores},
            "requires_review": ai_result.requires_review,
            "classification_vocabulary_status": "active_vocabulary_match",
            "recognition_context_version": recognition_context_version or rule_result.recognition_context_version,
        }
    )


def _request_payload(
    redacted_text: str,
    supported_document_types: list[str],
    rule_result: ClassificationResult,
    active_recognition_context: dict[str, Any],
) -> dict[str, Any]:
    system_prompt = (
        "Classify a financial source document for the Stats app. "
        "Return only compact JSON with document_type, document_subtype, confidence, "
        "reason_codes, explanation, requires_review, and vocabulary_status. "
        "Prefer active_recognition_context labels when they fit. Propose a new label only when no active label fits."
    )
    user_prompt = {
        "supported_document_types": supported_document_types,
        "active_recognition_context": active_recognition_context,
        "rule_result": rule_result.model_dump(),
        "redacted_text": redacted_text,
    }
    if settings.classification_ai_provider == "gemini":
        return {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(user_prompt, ensure_ascii=True)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

    return {
        "model": settings.classification_ai_model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=True)},
        ],
    }


def _request_headers(api_key: str) -> dict[str, str]:
    if settings.classification_ai_provider == "gemini":
        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _request_endpoint() -> str:
    if settings.classification_ai_endpoint:
        return settings.classification_ai_endpoint
    if settings.classification_ai_provider == "gemini":
        model_name = settings.classification_ai_model.strip()
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    return ""


def _parse_ai_response(raw_response: str, supported_document_types: list[str]) -> ClassificationResult | None:
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

    document_type = str(parsed.get("document_type", "unknown")).lower()
    document_subtype = str(parsed.get("document_subtype", "unknown")).lower()
    vocabulary_status = str(parsed.get("vocabulary_status") or "active_vocabulary_match").strip().lower()
    supported = {value.lower() for value in supported_document_types}
    if document_type not in supported and vocabulary_status != "outside_vocabulary_proposal":
        return None
    if not re.match(r"^[a-z][a-z0-9_]{1,79}$", document_type):
        return None
    if not re.match(r"^[a-z][a-z0-9_]{1,99}$", document_subtype):
        return None

    try:
        confidence = float(parsed.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0

    reason_codes = parsed.get("reason_codes")
    if not isinstance(reason_codes, list):
        reason_codes = ["AI_ASSISTED_CLASSIFICATION"]

    return ClassificationResult(
        document_type=document_type,
        document_subtype=document_subtype or "unknown",
        confidence=round(max(0.0, min(confidence, 1.0)), 3),
        status="classified" if confidence >= settings.classification_ai_min_confidence else "ambiguous",
        reason_codes=[str(code) for code in reason_codes],
        scores={f"ai.{document_type}.{document_subtype}": round(max(0.0, min(confidence, 1.0)), 3)},
        classification_source="ai_assist",
        ai_model_name=settings.classification_ai_model,
        ai_model_version=settings.classification_ai_model_version or settings.classification_ai_model,
        ai_confidence=round(max(0.0, min(confidence, 1.0)), 3),
        requires_review=bool(parsed.get("requires_review", confidence < settings.classification_ai_min_confidence)),
        review_reason_codes=["AI_CLASSIFICATION_REVIEW_REQUIRED"] if parsed.get("requires_review") else [],
        classification_vocabulary_status=vocabulary_status,
    )


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
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None
