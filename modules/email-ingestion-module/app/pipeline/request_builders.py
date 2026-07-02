"""M12 - Email Ingestion Module Start
Automated pipeline request builders.

Pure dict transforms that mirror the request shapes the manual Upload flow already
sends to M7 (extraction) and M8 (validation). Kept dependency-free (no httpx) so the
contract mapping can be unit-tested in isolation. These mirror
`BuildExtractionRequest` / `BuildValidationRequest` in apps/stats-web/Program.cs;
keep them in sync if those contracts change.
M12 End"""

from typing import Any


def build_extraction_request(parse_result: dict) -> dict:
    document_info = parse_result.get("document") or {}
    classification = parse_result.get("classification") or {}
    return {
        "parse_id": parse_result.get("parse_id"),
        "document": {
            "original_filename": document_info.get("original_filename"),
            "normalized_filename": document_info.get("normalized_filename"),
            "ingestion_id": document_info.get("ingestion_id"),
            "source_type": document_info.get("source_type"),
            "source_id": document_info.get("source_id"),
            "sha256": document_info.get("sha256"),
        },
        "document_type": classification.get("document_type")
        or document_info.get("document_type")
        or "unknown",
        "classification_confidence": classification.get("confidence"),
        "classification": classification,
        "text": parse_result.get("text") or "",
        "pages": parse_result.get("pages") or [],
        "metadata": parse_result.get("metadata") or {},
        "quality": parse_result.get("quality"),
        "findings": parse_result.get("findings") or [],
    }


def build_validation_request(extraction_result: dict, recognition_context: dict) -> dict:
    classification = extraction_result.get("classification") or {}
    return {
        "extraction_id": extraction_result.get("extraction_id"),
        "parse_id": extraction_result.get("parse_id"),
        "document": extraction_result.get("document"),
        "document_type": extraction_result.get("document_type"),
        "document_type_confidence": classification.get("confidence"),
        "document_type_status": classification.get("status"),
        "document_type_reason_codes": classification.get("reason_codes") or [],
        "document_recognition_suggestion_id": classification.get("recognition_suggestion_id"),
        "document_recognition_suggestion_status": classification.get("recognition_suggestion_status") or "none",
        "suggested_document_type": classification.get("suggested_document_type"),
        "suggested_document_subtype": classification.get("suggested_document_subtype"),
        "document_suggestion_confidence": classification.get("suggestion_confidence"),
        "document_suggestion_reason_codes": classification.get("suggestion_reason_codes") or [],
        "document_suggestion_source": classification.get("suggestion_source"),
        "document_suggestion_evidence_ref": classification.get("suggestion_evidence_ref"),
        "transaction_candidates": extraction_result.get("transaction_candidates") or [],
        "financial_field_candidates": extraction_result.get("financial_field_candidates") or [],
        "section_candidates": extraction_result.get("section_candidates") or [],
        "entity_candidates": extraction_result.get("entity_candidates") or [],
        "reference_candidates": extraction_result.get("reference_candidates") or [],
        "line_item_candidates": extraction_result.get("line_item_candidates") or [],
        "installment_candidates": extraction_result.get("installment_candidates") or [],
        "reconciliation": extraction_result.get("reconciliation"),
        "active_recognition_context": recognition_context or {},
        "findings": extraction_result.get("findings") or [],
    }


def text_at(payload: Any, key: str) -> str | None:
    if isinstance(payload, dict):
        value = payload.get(key)
        if value is not None:
            return str(value)
    return None


def int_at(payload: Any, key: str) -> int:
    if isinstance(payload, dict):
        try:
            return int(payload.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    return 0
