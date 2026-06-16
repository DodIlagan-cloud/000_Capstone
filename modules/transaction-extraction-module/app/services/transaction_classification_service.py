"""M7 - Transaction Extraction Module Start
Classifies extracted transactions using shared vocabulary and rule signals.
M7 End"""

import json
import re
import uuid
import time
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import settings
from app.models.extraction import TransactionCandidate
from app.services.ai_transaction_classification_service import (
    ai_classification_failure_reason,
    ai_classify_transaction,
    ai_skip_reason,
    merge_rule_and_ai_classification,
    should_try_ai_classification,
)


_active_settings_cache: tuple[float, dict[str, Any]] | None = None


def classify_transaction_candidate(
    candidate: TransactionCandidate,
    *,
    document_type: str,
    document_subtype: str = "unknown",
) -> TransactionCandidate:
    active_settings = _load_active_settings()
    if not active_settings:
        classification_source = (
            "ai_skipped_settings_unavailable"
            if settings.transaction_classification_ai_enabled
            else "settings_unavailable"
        )
        review_reason_codes = ["RECOGNITION_SETTINGS_UNAVAILABLE"]
        if settings.transaction_classification_ai_enabled:
            review_reason_codes.append("AI_SKIPPED_SETTINGS_UNAVAILABLE")
        unavailable = _unknown(
            "unknown",
            "unknown",
            0.0,
            ["RECOGNITION_SETTINGS_UNAVAILABLE"],
            {},
        )
        uncategorized = _unknown(
            "uncategorized",
            "unknown",
            0.0,
            ["RECOGNITION_SETTINGS_UNAVAILABLE"],
            {},
        )
        updates = {
            "transaction_type": unavailable["label"],
            "transaction_subtype": unavailable["subtype"],
            "transaction_type_confidence": unavailable["confidence"],
            "transaction_type_status": unavailable["status"],
            "transaction_type_reason_codes": unavailable["reason_codes"],
            "transaction_type_scores": unavailable["scores"],
            "spending_category": uncategorized["label"],
            "spending_subcategory": uncategorized["subtype"],
            "spending_category_confidence": uncategorized["confidence"],
            "spending_category_status": uncategorized["status"],
            "spending_category_reason_codes": uncategorized["reason_codes"],
            "spending_category_scores": uncategorized["scores"],
            "classification_source": classification_source,
            "classification_review_required": True,
            "classification_review_reason_codes": sorted(set(review_reason_codes)),
            "classification_vocabulary_status": "settings_unavailable",
        }
        if hasattr(candidate, "model_copy"):
            return candidate.model_copy(update=updates)
        return candidate.copy(update=updates)

    learned_result = _learned_merchant_classification(
        candidate=candidate,
        document_type=document_type,
        document_subtype=document_subtype,
        active_settings=active_settings,
    )
    if learned_result and learned_result.get("match_status") == "matched":
        return _apply_learned_merchant_classification(
            candidate=candidate,
            learned_result=learned_result,
            active_settings=active_settings,
        )
    learned_review_codes = _learned_review_codes(learned_result)

    transaction_result = _classify(
        text=_transaction_context(candidate, document_type, document_subtype),
        rules=active_settings.get("transaction_rules", {}),
        vocabulary=active_settings.get("transaction_vocabulary", {}),
        label_key="transaction_type",
        subtype_key="transaction_subtype",
        labels_key="transaction_types",
        subtypes_key="transaction_subtypes",
        default_label="unknown",
        default_subtype="unknown",
        threshold=settings.transaction_classification_threshold,
    )
    transaction_result = _statement_debit_purchase_fallback(
        candidate=candidate,
        document_type=document_type,
        document_subtype=document_subtype,
        transaction_result=transaction_result,
        active_settings=active_settings,
    )
    category_result = _classify(
        text=_category_context(candidate, document_type, document_subtype, transaction_result),
        rules=active_settings.get("spending_rules", {}),
        vocabulary=active_settings.get("spending_vocabulary", {}),
        label_key="spending_category",
        subtype_key="spending_subcategory",
        labels_key="spending_categories",
        subtypes_key="spending_subcategories",
        default_label="uncategorized",
        default_subtype="unknown",
        threshold=settings.spending_category_threshold,
    )
    category_result = _merchant_spending_category_fallback(
        candidate=candidate,
        transaction_result=transaction_result,
        category_result=category_result,
        active_settings=active_settings,
    )

    ai_result = None
    ai_was_eligible = should_try_ai_classification(transaction_result, category_result)
    ai_skip_code = None
    if ai_was_eligible:
        ai_skip_code = ai_skip_reason()
        ai_result = ai_classify_transaction(
            candidate=candidate,
            document_type=document_type,
            document_subtype=document_subtype,
            transaction_result=transaction_result,
            category_result=category_result,
            active_recognition_context=_transaction_ai_context(active_settings),
        )
    rule_transaction_result = transaction_result
    rule_category_result = category_result
    merged = merge_rule_and_ai_classification(
        candidate=candidate,
        rule_transaction=transaction_result,
        rule_category=category_result,
        ai_result=ai_result,
    )
    transaction_result = merged["transaction"]
    category_result = merged["category"]
    transaction_result = _derive_parent_from_child(
        transaction_result,
        active_settings.get("transaction_vocabulary", {}),
        subtypes_key="transaction_subtypes",
    )
    category_result = _derive_parent_from_child(
        category_result,
        active_settings.get("spending_vocabulary", {}),
        subtypes_key="spending_subcategories",
    )
    suggestion_updates = _suggestion_updates(
        candidate=candidate,
        document_type=document_type,
        document_subtype=document_subtype,
        ai_result=ai_result,
        merged=merged,
        active_settings=active_settings,
        rule_transaction_result=rule_transaction_result,
        rule_category_result=rule_category_result,
    )
    updates = {
        "transaction_type": transaction_result["label"],
        "transaction_subtype": transaction_result["subtype"],
        "transaction_type_confidence": transaction_result["confidence"],
        "transaction_type_status": transaction_result["status"],
        "transaction_type_reason_codes": transaction_result["reason_codes"],
        "transaction_type_scores": transaction_result["scores"],
        "spending_category": category_result["label"],
        "spending_subcategory": category_result["subtype"],
        "spending_category_confidence": category_result["confidence"],
        "spending_category_status": category_result["status"],
        "spending_category_reason_codes": category_result["reason_codes"],
        "spending_category_scores": category_result["scores"],
        "classification_source": merged["classification_source"],
        "ai_model_name": merged["ai_model_name"],
        "ai_model_version": merged["ai_model_version"],
        "ai_confidence": merged["ai_confidence"],
        "classification_review_required": merged["classification_review_required"],
        "classification_review_reason_codes": merged["classification_review_reason_codes"],
        "recognition_context_version": _recognition_context_version(active_settings),
        "classification_vocabulary_status": "active_vocabulary_match",
        **suggestion_updates,
    }
    if learned_review_codes:
        updates["classification_review_required"] = True
        updates["classification_review_reason_codes"] = sorted(
            set([*list(updates.get("classification_review_reason_codes") or []), *learned_review_codes])
        )
    if ai_was_eligible and ai_result is None and settings.transaction_classification_ai_enabled:
        if not ai_skip_code:
            ai_skip_code = ai_classification_failure_reason() or "AI_SKIPPED_PROVIDER_NO_RESULT"
        updates["classification_source"] = str(ai_skip_code).lower()
        updates["classification_review_required"] = True
        updates["classification_review_reason_codes"] = sorted(
            set([*list(updates.get("classification_review_reason_codes") or []), ai_skip_code])
        )
    if hasattr(candidate, "model_copy"):
        return candidate.model_copy(update=updates)
    return candidate.copy(update=updates)


def _learned_merchant_classification(
    *,
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    active_settings: dict[str, Any],
) -> dict[str, Any] | None:
    if not settings.merchant_classification_lookup_url:
        return None
    if str(candidate.direction or "").lower() == "credit":
        return None
    query = urlencode(
        {
            "description": candidate.description,
        }
    )
    separator = "&" if "?" in settings.merchant_classification_lookup_url else "?"
    try:
        request = Request(f"{settings.merchant_classification_lookup_url}{separator}{query}")
        if settings.recognition_settings_internal_key:
            request.add_header("X-Stats-Internal-Key", settings.recognition_settings_internal_key)
        with urlopen(request, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, TimeoutError, HTTPError, URLError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _apply_learned_merchant_classification(
    *,
    candidate: TransactionCandidate,
    learned_result: dict[str, Any],
    active_settings: dict[str, Any],
) -> TransactionCandidate:
    transaction_type = str(learned_result.get("transaction_type") or "unknown").lower()
    transaction_subtype = str(learned_result.get("transaction_subtype") or "unknown").lower()
    spending_category = str(learned_result.get("spending_category") or "uncategorized").lower()
    spending_subcategory = str(learned_result.get("spending_subcategory") or "unknown").lower()
    confidence = _learned_confidence(learned_result)
    reason_codes = sorted(set(str(code) for code in learned_result.get("reason_codes") or []))
    if "PRIOR_MERCHANT_CLASSIFICATION_REUSED" not in reason_codes:
        reason_codes.append("PRIOR_MERCHANT_CLASSIFICATION_REUSED")

    if not _is_allowed_label(
        active_settings.get("transaction_vocabulary", {}),
        labels_key="transaction_types",
        subtypes_key="transaction_subtypes",
        label=transaction_type,
        subtype=transaction_subtype,
    ) or not _is_allowed_label(
        active_settings.get("spending_vocabulary", {}),
        labels_key="spending_categories",
        subtypes_key="spending_subcategories",
        label=spending_category,
        subtype=spending_subcategory,
    ):
        review_codes = sorted(set([*reason_codes, "PRIOR_MERCHANT_CLASSIFICATION_PARENT_CHILD_MISMATCH"]))
        updates = {
            "classification_review_required": True,
            "classification_review_reason_codes": review_codes,
            "classification_source": "prior_merchant_human_confirmed",
            "classification_vocabulary_status": "outside_vocabulary_proposal",
        }
    else:
        updates = {
            "transaction_type": transaction_type,
            "transaction_subtype": transaction_subtype,
            "transaction_type_confidence": confidence,
            "transaction_type_status": "classified",
            "transaction_type_reason_codes": reason_codes,
            "transaction_type_scores": {f"prior_merchant.{transaction_type}.{transaction_subtype}": confidence},
            "spending_category": spending_category,
            "spending_subcategory": spending_subcategory,
            "spending_category_confidence": confidence,
            "spending_category_status": "classified",
            "spending_category_reason_codes": reason_codes,
            "spending_category_scores": {f"prior_merchant.{spending_category}.{spending_subcategory}": confidence},
            "classification_source": "prior_merchant_human_confirmed",
            "ai_model_name": None,
            "ai_model_version": None,
            "ai_confidence": None,
            "classification_review_required": False,
            "classification_review_reason_codes": [],
            "recognition_suggestion_id": None,
            "recognition_suggestion_status": "none",
            "suggested_transaction_type": None,
            "suggested_transaction_subtype": None,
            "suggested_spending_category": None,
            "suggested_spending_subcategory": None,
            "suggestion_confidence": None,
            "suggestion_reason_codes": [],
            "suggestion_source": None,
            "suggestion_evidence_ref": None,
            "classification_vocabulary_status": "active_vocabulary_match",
            "recognition_context_version": _recognition_context_version(active_settings),
        }
    if hasattr(candidate, "model_copy"):
        return candidate.model_copy(update=updates)
    return candidate.copy(update=updates)


def _learned_review_codes(learned_result: dict[str, Any] | None) -> list[str]:
    if not learned_result:
        return []
    status = str(learned_result.get("match_status") or "").lower()
    if status == "conflicted":
        return ["PRIOR_MERCHANT_CLASSIFICATION_CONFLICT"]
    if status == "inactive":
        return ["PRIOR_MERCHANT_CLASSIFICATION_INACTIVE"]
    if status == "unsafe":
        return ["PRIOR_MERCHANT_CLASSIFICATION_PARENT_CHILD_MISMATCH"]
    return []


def _learned_confidence(learned_result: dict[str, Any]) -> float:
    try:
        return round(float(learned_result.get("profile_confidence") or 0.9), 3)
    except (TypeError, ValueError):
        return 0.9


def _recognition_context_version(active_settings: dict[str, Any] | None) -> str | None:
    if not active_settings:
        return None
    context = active_settings.get("recognition_context")
    if isinstance(context, dict) and context.get("version"):
        return str(context["version"])
    if active_settings.get("recognition_context_version"):
        return str(active_settings["recognition_context_version"])
    return None


def _transaction_ai_context(active_settings: dict[str, Any]) -> dict[str, Any]:
    context = active_settings.get("recognition_context")
    if isinstance(context, dict):
        compact = {"version": context.get("version") or active_settings.get("recognition_context_version")}
        if isinstance(context.get("transaction"), dict):
            compact["transaction"] = context["transaction"]
        if isinstance(context.get("spending"), dict):
            compact["spending"] = context["spending"]
        return compact
    return {
        "version": _recognition_context_version(active_settings),
        "transaction": {
            "vocabulary": active_settings.get("transaction_vocabulary", {}),
            "rules": active_settings.get("transaction_rules", {}),
        },
        "spending": {
            "vocabulary": active_settings.get("spending_vocabulary", {}),
            "rules": active_settings.get("spending_rules", {}),
        },
    }


def _statement_debit_purchase_fallback(
    *,
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    transaction_result: dict[str, object],
    active_settings: dict[str, Any],
) -> dict[str, object]:
    if transaction_result.get("status") == "classified":
        return transaction_result
    if str(candidate.direction or "").lower() != "debit":
        return transaction_result
    if document_type != "statement" or document_subtype != "credit_card_statement":
        return transaction_result
    if (candidate.source.section_label or "").lower() != "transaction_table":
        return transaction_result
    if _looks_like_non_purchase_statement_debit(candidate):
        return transaction_result
    if not _is_allowed_label(
        active_settings.get("transaction_vocabulary", {}),
        labels_key="transaction_types",
        subtypes_key="transaction_subtypes",
        label="purchase",
        subtype="merchant_purchase",
    ):
        return transaction_result
    scores = dict(transaction_result.get("scores") or {})
    scores["statement.debit.purchase.merchant_purchase"] = 0.78
    return {
        "label": "purchase",
        "subtype": "merchant_purchase",
        "confidence": 0.78,
        "status": "classified",
        "reason_codes": sorted(
            set([*list(transaction_result.get("reason_codes") or []), "CREDIT_CARD_STATEMENT_DEBIT_PURCHASE"])
        ),
        "scores": scores,
        "inactive_suggestions": transaction_result.get("inactive_suggestions") or [],
    }


def _looks_like_non_purchase_statement_debit(candidate: TransactionCandidate) -> bool:
    text = " ".join(
        [
            candidate.description,
            candidate.source.text,
            " ".join(candidate.reason_codes),
        ]
    ).lower()
    return bool(
        re.search(
            r"\b(paid\s+thru|payment|cash\s+advance|finance\s+charge|late\s+payment|service\s+fee|interest|annual\s+fee)\b",
            text,
        )
    )


def _merchant_spending_category_fallback(
    *,
    candidate: TransactionCandidate,
    transaction_result: dict[str, object],
    category_result: dict[str, object],
    active_settings: dict[str, Any],
) -> dict[str, object]:
    if category_result.get("status") == "classified":
        return category_result
    if transaction_result.get("label") != "purchase" or transaction_result.get("subtype") != "merchant_purchase":
        return category_result
    merchant_category = _known_merchant_category(candidate.description)
    if not merchant_category:
        return category_result
    label, subtype, reason_code = merchant_category
    if not _is_allowed_label(
        active_settings.get("spending_vocabulary", {}),
        labels_key="spending_categories",
        subtypes_key="spending_subcategories",
        label=label,
        subtype=subtype,
    ):
        return category_result
    scores = dict(category_result.get("scores") or {})
    scores[f"merchant.category.{label}.{subtype}"] = 0.86
    return {
        "label": label,
        "subtype": subtype,
        "confidence": 0.86,
        "status": "classified",
        "reason_codes": sorted(set([*list(category_result.get("reason_codes") or []), reason_code])),
        "scores": scores,
        "inactive_suggestions": category_result.get("inactive_suggestions") or [],
    }


def _known_merchant_category(description: str) -> tuple[str, str, str] | None:
    normalized = " ".join(description.lower().split())
    if "superbowl" in normalized:
        return "food_dining", "restaurant", "KNOWN_RESTAURANT_MERCHANT"
    return None


def _suggestion_updates(
    *,
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    ai_result: dict[str, object] | None,
    merged: dict[str, object],
    active_settings: dict[str, Any],
    rule_transaction_result: dict[str, object],
    rule_category_result: dict[str, object],
) -> dict[str, object]:
    if ai_result is None or not str(merged.get("classification_source") or "").startswith("ai"):
        inactive_transaction = _top_inactive_suggestion(rule_transaction_result)
        inactive_category = _top_inactive_suggestion(rule_category_result)
        if not inactive_transaction and not inactive_category:
            fallback = _receipt_like_pending_suggestion(candidate, document_type, document_subtype)
            inactive_transaction = fallback.get("transaction")
            inactive_category = fallback.get("category")
        if not inactive_transaction and not inactive_category:
            return {}
        suggested_transaction_type = str((inactive_transaction or {}).get("label") or "unknown").lower()
        suggested_transaction_subtype = str((inactive_transaction or {}).get("subtype") or "unknown").lower()
        suggested_spending_category = str((inactive_category or {}).get("label") or "uncategorized").lower()
        suggested_spending_subcategory = str((inactive_category or {}).get("subtype") or "unknown").lower()
        suggestion_source = "rules"
        suggestion_confidence = max(
            float((inactive_transaction or {}).get("confidence") or 0.0),
            float((inactive_category or {}).get("confidence") or 0.0),
        )
        suggestion_reason_codes = sorted(
            set(
                [
                    *[str(code) for code in (inactive_transaction or {}).get("reason_codes") or []],
                    *[str(code) for code in (inactive_category or {}).get("reason_codes") or []],
                    "INACTIVE_RECOGNITION_LABEL_SUGGESTION",
                ]
            )
        )
    else:
        suggested_transaction_type = str(ai_result.get("transaction_type") or "unknown").lower()
        suggested_transaction_subtype = str(ai_result.get("transaction_subtype") or "unknown").lower()
        suggested_spending_category = str(ai_result.get("spending_category") or "uncategorized").lower()
        suggested_spending_subcategory = str(ai_result.get("spending_subcategory") or "unknown").lower()
        suggestion_source = "ai"
        suggestion_confidence = merged.get("ai_confidence")
        suggestion_reason_codes = [str(code) for code in ai_result.get("reason_codes") or []]
    suggested_transaction_type = (
        _parent_for_child(
            active_settings.get("transaction_vocabulary", {}),
            subtypes_key="transaction_subtypes",
            child=suggested_transaction_subtype,
        )
        or suggested_transaction_type
    )
    suggested_spending_category = (
        _parent_for_child(
            active_settings.get("spending_vocabulary", {}),
            subtypes_key="spending_subcategories",
            child=suggested_spending_subcategory,
        )
        or suggested_spending_category
    )
    transaction_known = _is_allowed_label(
        active_settings.get("transaction_vocabulary", {}),
        labels_key="transaction_types",
        subtypes_key="transaction_subtypes",
        label=suggested_transaction_type,
        subtype=suggested_transaction_subtype,
    )
    category_known = _is_allowed_label(
        active_settings.get("spending_vocabulary", {}),
        labels_key="spending_categories",
        subtypes_key="spending_subcategories",
        label=suggested_spending_category,
        subtype=suggested_spending_subcategory,
    )
    if transaction_known and category_known:
        return {}

    suggestion_id = _suggestion_id(
        candidate,
        {
            "transaction_type": suggested_transaction_type,
            "transaction_subtype": suggested_transaction_subtype,
            "spending_category": suggested_spending_category,
            "spending_subcategory": suggested_spending_subcategory,
        },
    )
    reason_codes = sorted(
        set(
            [
                *suggestion_reason_codes,
                "AI_RECOGNITION_LABEL_SUGGESTION" if suggestion_source == "ai" else "RULE_RECOGNITION_LABEL_SUGGESTION",
            ]
        )
    )
    updates: dict[str, object] = {
        "recognition_suggestion_id": suggestion_id,
        "recognition_suggestion_status": "pending",
        "suggested_transaction_type": suggested_transaction_type,
        "suggested_transaction_subtype": suggested_transaction_subtype,
        "suggested_spending_category": suggested_spending_category,
        "suggested_spending_subcategory": suggested_spending_subcategory,
        "suggestion_confidence": suggestion_confidence,
        "suggestion_reason_codes": reason_codes,
        "suggestion_source": suggestion_source,
        "suggestion_evidence_ref": f"candidate:{candidate.candidate_id}",
        "classification_review_required": True,
        "classification_review_reason_codes": sorted(
            set([*list(merged.get("classification_review_reason_codes") or []), "PENDING_RECOGNITION_LABEL_SUGGESTION"])
        ),
    }
    updates["classification_vocabulary_status"] = "outside_vocabulary_proposal"
    updates["classification_confirmation_mode"] = "transaction_review_save"
    if suggestion_source == "ai":
        updates["recognition_suggestion_status"] = "outside_vocabulary"
        updates["classification_review_reason_codes"] = sorted(
            set(
                [
                    *list(updates.get("classification_review_reason_codes") or []),
                    "AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED",
                    "UNAPPROVED_RECOGNITION_LABEL",
                ]
            )
        )
    return updates


def _is_allowed_label(
    vocabulary: dict[str, Any],
    *,
    labels_key: str,
    subtypes_key: str,
    label: str,
    subtype: str,
) -> bool:
    allowed_labels = {str(value).lower() for value in vocabulary.get(labels_key, [])}
    allowed_subtypes = {
        str(key).lower(): {str(value).lower() for value in values}
        for key, values in (vocabulary.get(subtypes_key, {}) or {}).items()
    }
    return label in allowed_labels and subtype in allowed_subtypes.get(label, set())


def _derive_parent_from_child(
    result: dict[str, object],
    vocabulary: dict[str, Any],
    *,
    subtypes_key: str,
) -> dict[str, object]:
    subtype = str(result.get("subtype") or "unknown").lower()
    if not subtype or subtype == "unknown":
        return result
    parent = _parent_for_child(vocabulary, subtypes_key=subtypes_key, child=subtype)
    if not parent or parent == str(result.get("label") or "").lower():
        return result
    next_result = dict(result)
    next_result["label"] = parent
    reason_codes = set(str(code) for code in next_result.get("reason_codes") or [])
    reason_codes.add("PARENT_DERIVED_FROM_SUBTYPE")
    next_result["reason_codes"] = sorted(reason_codes)
    return next_result


def _parent_for_child(vocabulary: dict[str, Any], *, subtypes_key: str, child: str) -> str | None:
    child_key = str(child or "").lower()
    if child_key in {"", "unknown", "uncategorized"}:
        return None
    for parent, children in (vocabulary.get(subtypes_key, {}) or {}).items():
        if child_key in {str(value).lower() for value in children or []}:
            return str(parent).lower()
    return None


def _ranked_inactive_suggestions(inactive_rules: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(inactive_rules, key=lambda item: float(item.get("confidence") or 0.0), reverse=True)


def _top_inactive_suggestion(result: dict[str, object]) -> dict[str, object] | None:
    suggestions = result.get("inactive_suggestions")
    if not isinstance(suggestions, list) or not suggestions:
        return None
    first = suggestions[0]
    return first if isinstance(first, dict) else None


def _receipt_like_pending_suggestion(
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
) -> dict[str, dict[str, object] | None]:
    text = " ".join(
        [
            document_type,
            document_subtype,
            candidate.description,
            candidate.source.text,
            candidate.source.section_label or "",
            " ".join(candidate.reason_codes),
        ]
    ).lower()
    receipt_signals = [
        "receipt",
        "tax invoice",
        "total",
        "gst",
        "eftpos",
        "card",
        "approved",
        "ocr_receipt_total_fallback",
        "receipt_totals",
    ]
    if not any(signal in text for signal in receipt_signals):
        return {"transaction": None, "category": None}
    if str(candidate.direction or "").lower() != "debit" or float(candidate.amount or 0) <= 0:
        return {"transaction": None, "category": None}

    category_label = "shopping"
    category_subtype = "general_merchandise"
    if any(signal in text for signal in ["fuel", "petrol", "diesel", "parking", "transport", "fare"]):
        category_label = "transport"
        category_subtype = "public_transport" if "fare" in text else "fuel"
    elif any(signal in text for signal in ["restaurant", "cafe", "dining", "takeaway", "food"]):
        category_label = "food_dining"
        category_subtype = "unknown"
    elif any(signal in text for signal in ["pharmacy", "medical", "clinic", "doctor", "chemist"]):
        category_label = "medical"
        category_subtype = "unknown"

    return {
        "transaction": {
            "label": "purchase",
            "subtype": "card_purchase" if any(signal in text for signal in ["card", "eftpos"]) else "unknown",
            "confidence": 0.78,
            "reason_codes": ["RECEIPT_LIKE_DEBIT_PURCHASE_SUGGESTION"],
        },
        "category": {
            "label": category_label,
            "subtype": category_subtype,
            "confidence": 0.68,
            "reason_codes": ["RECEIPT_LIKE_SPENDING_CATEGORY_SUGGESTION"],
        },
    }


def _suggestion_id(candidate: TransactionCandidate, ai_result: dict[str, object]) -> str:
    material = "|".join(
        [
            candidate.candidate_id,
            str(ai_result.get("transaction_type") or ""),
            str(ai_result.get("transaction_subtype") or ""),
            str(ai_result.get("spending_category") or ""),
            str(ai_result.get("spending_subcategory") or ""),
        ]
    )
    return f"suggestion_{uuid.uuid5(uuid.NAMESPACE_URL, material).hex[:24]}"


def _classify(
    *,
    text: str,
    rules: dict[str, Any],
    vocabulary: dict[str, Any],
    label_key: str,
    subtype_key: str,
    labels_key: str,
    subtypes_key: str,
    default_label: str,
    default_subtype: str,
    threshold: float,
) -> dict[str, object]:
    normalized_text = " ".join((text or "").lower().split())
    allowed_labels = {label.lower() for label in vocabulary.get(labels_key, [])}
    allowed_subtypes = {
        label.lower(): {subtype.lower() for subtype in subtypes}
        for label, subtypes in vocabulary.get(subtypes_key, {}).items()
    }
    scored_rules = []
    inactive_rules = []
    scores: dict[str, float] = {}
    reason_codes: list[str] = []

    for rule in rules.get("rules", []):
        label = str(rule.get(label_key, default_label)).lower()
        subtype = str(rule.get(subtype_key, default_subtype)).lower()
        score, matched = _score_rule(normalized_text, rule)
        if score <= 0:
            continue
        if _rule_blocked_by_context(normalized_text, rule, matched):
            continue
        key = f"{label}.{subtype}"
        scores[key] = round(score, 3)
        rule_reason = str(rule.get("reason_code") or f"{label.upper()}_SIGNALS")
        if label not in allowed_labels or subtype not in allowed_subtypes.get(label, {default_subtype}):
            inactive_rules.append(
                {
                    "label": label,
                    "subtype": subtype,
                    "confidence": round(score, 3),
                    "reason_codes": [rule_reason, "INACTIVE_RECOGNITION_LABEL_SIGNAL"],
                    "matched": matched,
                }
            )
            continue
        if score >= float(rule.get("minimum_score", 0.0)):
            reason_codes.append(rule_reason)
        scored_rules.append((label, subtype, score, matched, rule))

    if not scored_rules:
        reason = "INACTIVE_RECOGNITION_LABEL_SIGNAL" if inactive_rules else "NO_CLASSIFICATION_SIGNALS"
        result = _unknown(default_label, default_subtype, 0.0, [reason], scores)
        result["inactive_suggestions"] = _ranked_inactive_suggestions(inactive_rules)
        return result

    best_label, best_subtype, best_score, _matched, _rule = max(scored_rules, key=lambda item: item[2])
    confidence = round(best_score, 3)
    sorted_scores = sorted((item[2] for item in scored_rules), reverse=True)
    ambiguous = len(sorted_scores) > 1 and sorted_scores[0] > 0 and abs(sorted_scores[0] - sorted_scores[1]) < 0.10

    if confidence >= threshold and not ambiguous:
        return {
            "label": best_label,
            "subtype": best_subtype,
            "confidence": confidence,
            "status": "classified",
            "reason_codes": sorted(set(reason_codes)),
            "scores": scores,
            "inactive_suggestions": _ranked_inactive_suggestions(inactive_rules),
        }
    if ambiguous:
        result = _unknown(default_label, default_subtype, confidence, [*reason_codes, "AMBIGUOUS_CLASSIFICATION_SIGNALS"], scores, "ambiguous")
        result["inactive_suggestions"] = _ranked_inactive_suggestions(inactive_rules)
        return result
    result = _unknown(default_label, default_subtype, confidence, [*reason_codes, "CONFIDENCE_BELOW_THRESHOLD"], scores)
    result["inactive_suggestions"] = _ranked_inactive_suggestions(inactive_rules)
    return result


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


def _rule_blocked_by_context(text: str, rule: dict[str, Any], matched: list[str]) -> bool:
    reason_code = str(rule.get("reason_code") or "").upper()
    if reason_code != "REFUND_REVERSAL_SIGNALS":
        return False
    if "direction:debit" not in text:
        return False

    # "credit" and "statement" are common credit-card context words; they are not
    # enough to call a debit merchant row a refund/reversal.
    explicit_refund_signals = {"refund", "reversal", "cashback", "returned"}
    if any(signal in explicit_refund_signals for signal in matched):
        return False
    if re.search(r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2}|,\d{2})cr\b", text, re.IGNORECASE):
        return False
    return True


def _contains_signal(text: str, signal: str) -> bool:
    escaped = re.escape(" ".join(signal.split()))
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text))


def _unknown(
    label: str,
    subtype: str,
    confidence: float,
    reason_codes: list[str],
    scores: dict[str, float],
    status: str = "unknown",
) -> dict[str, object]:
    return {
        "label": label,
        "subtype": subtype,
        "confidence": round(confidence, 3),
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "scores": scores,
    }


def _transaction_context(candidate: TransactionCandidate, document_type: str, document_subtype: str) -> str:
    return " ".join(
        [
            f"document_type:{document_type}",
            f"document_subtype:{document_subtype}",
            f"direction:{candidate.direction}",
            f"section:{candidate.source.section_label or ''}",
            candidate.description,
            candidate.source.text,
            " ".join(candidate.reason_codes),
        ]
    )


def _category_context(
    candidate: TransactionCandidate,
    document_type: str,
    document_subtype: str,
    transaction_result: dict[str, object],
) -> str:
    return " ".join(
        [
            f"document_type:{document_type}",
            f"document_subtype:{document_subtype}",
            f"transaction_type:{transaction_result['label']}",
            f"transaction_subtype:{transaction_result['subtype']}",
            f"direction:{candidate.direction}",
            candidate.description,
            candidate.source.text,
            " ".join(candidate.reason_codes),
        ]
    )


def _load_transaction_vocabulary() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("transaction_vocabulary"), dict):
        return active["transaction_vocabulary"]
    return {}


def _load_transaction_rules() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("transaction_rules"), dict):
        return active["transaction_rules"]
    return {"rules": []}


def _load_category_vocabulary() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("spending_vocabulary"), dict):
        return active["spending_vocabulary"]
    return {}


def _load_category_rules() -> dict[str, Any]:
    active = _load_active_settings()
    if active and isinstance(active.get("spending_rules"), dict):
        return active["spending_rules"]
    return {"rules": []}


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


def _clear_settings_cache() -> None:
    global _active_settings_cache
    _active_settings_cache = None


_load_transaction_vocabulary.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
_load_transaction_rules.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
_load_category_vocabulary.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
_load_category_rules.cache_clear = _clear_settings_cache  # type: ignore[attr-defined]
