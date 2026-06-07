"""M9 - Stats Data and Persistence Start
Maps validation results into Stats Data staging and promoted reporting rows.
M9 End"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable


NAMESPACE = uuid.UUID("7a783aa3-f5a3-44be-98c7-0c571e44c31f")
DEFAULT_CURRENCY = "PHP"
VALIDATION_HANDOFF_DIR_ENV = "STATS_VALIDATION_HANDOFF_DIR"
LOGGER = logging.getLogger(__name__)

TABLE_PRIMARY_KEYS = {
    "validation_results": "validation_result_id",
    "stats_documents": "document_id",
    "processing_runs": "processing_run_id",
    "transaction_batches": "transaction_batch_id",
    "transactions": "transaction_id",
    "financial_fields": "financial_field_id",
    "statement_summaries": "statement_summary_id",
    "document_financial_summaries": "document_financial_summary_id",
    "document_sections": "document_section_id",
    "validated_entities": "validated_entity_id",
    "validated_references": "validated_reference_id",
    "line_items": "line_item_id",
    "installments": "installment_id",
    "findings": "finding_id",
    "review_items": "review_item_id",
    "duplicate_check_batches": "duplicate_check_id",
    "duplicate_check_results": "duplicate_check_result_id",
}


@dataclass(frozen=True)
class SqlOperation:
    table: str
    key_column: str
    values: dict[str, Any]


@dataclass(frozen=True)
class ValidationPersistencePlan:
    validation_id: str
    document_id: str
    validation_result_id: str
    operations: list[SqlOperation]


@dataclass(frozen=True)
class DeleteDocumentResult:
    document_id: str
    validation_result_id: str | None
    deleted_counts: dict[str, int]


@dataclass(frozen=True)
class UploadedDocumentSummary:
    document_id: str
    original_filename: str
    document_type: str | None
    status: str
    source_institution: str | None
    created_at_utc: str | None
    updated_at_utc: str | None
    uploaded_by_user_id: str | None
    storage_reference: str | None
    validation_result_id: str | None
    transaction_count: int
    financial_field_count: int
    review_item_count: int


def build_validation_persistence_plan(
    result: dict[str, Any],
    *,
    uploaded_by_user_id: str | None = None,
    storage_reference: str | None = None,
    saved_by_user_id: str | None = None,
) -> ValidationPersistencePlan:
    """Build deterministic staging and promoted-row operations for a validation result."""
    validation_id = _required_text(result, "validation_id")
    summary = result.get("summary") or {}
    evaluation = result.get("evaluation") or {}
    document = result.get("document") or {}
    document_type = _text(result.get("document_type")) or _text(evaluation.get("document_type")) or "unknown"
    ingestion_id = _text(document.get("ingestion_id")) or validation_id
    owner_id = uploaded_by_user_id or _text(document.get("uploaded_by_user_id"))
    result_id = _stable_id("validation", validation_id)
    document_id = _stable_id("document", validation_id, ingestion_id)
    batch_id = _stable_id("batch", validation_id)

    operations = [
        _op(
            "validation_results",
            {
                "validation_result_id": result_id,
                "validation_id": validation_id,
                "extraction_id": _text(result.get("extraction_id")),
                "parse_id": _text(result.get("parse_id")),
                "ingestion_id": _text(document.get("ingestion_id")),
                "uploaded_by_user_id": owner_id,
                "document_type": document_type,
                "status": _enum_value(result.get("status")),
                "document_review_status": _text(summary.get("document_review_status")),
                "recommended_action": _text(summary.get("recommended_action")),
                "normalized_record_count": _int(summary.get("normalized_record_count")),
                "valid_record_count": _int(summary.get("valid_record_count")),
                "warning_record_count": _int(summary.get("warning_record_count")),
                "invalid_record_count": _int(summary.get("invalid_record_count")),
                "duplicate_record_count": _int(summary.get("duplicate_record_count")),
                "review_item_count": _int(summary.get("review_item_count")),
                "section_candidate_count": _int(summary.get("section_candidate_count")),
                "entity_count": _int(summary.get("entity_count")),
                "reference_count": _int(summary.get("reference_count")),
                "line_item_count": _int(summary.get("line_item_count")),
                "installment_count": _int(summary.get("installment_count")),
                "warning_installment_count": _int(summary.get("warning_installment_count")),
                "invalid_installment_count": _int(summary.get("invalid_installment_count")),
                "debit_total": _money(summary.get("debit_total")),
                "credit_total": _money(summary.get("credit_total")),
                "net_total": _money(summary.get("net_total")),
                "reconciliation_delta": _money(summary.get("reconciliation_delta")),
                "payload_json": _json(result),
                "promotion_status": "pending",
            },
        ),
        _op(
            "stats_documents",
            {
                "document_id": document_id,
                "ingestion_id": _text(document.get("ingestion_id")),
                "uploaded_by_user_id": owner_id,
                "validation_result_id": result_id,
                "original_filename": _text(document.get("original_filename")) or "unknown",
                "normalized_filename": _text(document.get("normalized_filename")) or "unknown",
                "source_type": _text(document.get("source_type")) or "api",
                "source_id": _text(document.get("source_id")),
                "sha256": _text(document.get("sha256")),
                "document_fingerprint": _document_fingerprint(result),
                "detected_mime_type": _text(document.get("detected_mime_type")),
                "size_bytes": _int_or_none(document.get("size_bytes")),
                "storage_reference": _text(storage_reference) or _text(document.get("storage_reference")) or "",
                "document_type": document_type,
                "source_institution": _first_entity_value(result, "institution"),
                "status": _document_status(summary, result),
                "ocr_quality_status": _document_quality_status(result),
                "redaction_applied": 1,
            },
        ),
        _op(
            "processing_runs",
            {
                "processing_run_id": _stable_id("processing-run", validation_id, "validation"),
                "document_id": document_id,
                "parse_id": _text(result.get("parse_id")),
                "extraction_id": _text(result.get("extraction_id")),
                "validation_id": validation_id,
                "module_name": "Data Validation",
                "status": _enum_value(result.get("status")),
                "started_at_utc": _utc_now_token(),
                "completed_at_utc": _utc_now_token(),
                "summary_json": _json(summary),
                "finding_counts_json": _json(evaluation.get("finding_counts") or {}),
            },
        ),
        _op(
            "transaction_batches",
            {
                "transaction_batch_id": batch_id,
                "document_id": document_id,
                "validation_id": validation_id,
                "saved_by_user_id": saved_by_user_id or owner_id,
                "status": _batch_status(summary, result),
                "input_record_count": _int(summary.get("normalized_record_count")),
                "saved_record_count": _int(summary.get("valid_record_count")),
                "duplicate_record_count": _int(summary.get("duplicate_record_count")),
                "warning_record_count": _int(summary.get("warning_record_count")),
                "invalid_record_count": _int(summary.get("invalid_record_count")),
                "debit_total": _money(summary.get("debit_total")),
                "credit_total": _money(summary.get("credit_total")),
                "net_total": _money(summary.get("net_total")),
            },
        ),
    ]

    for section in result.get("section_candidates") or []:
        operations.append(_document_section_op(section, document_id, validation_id))
    for record in result.get("normalized_records") or []:
        operations.append(_transaction_op(record, document_id, batch_id, owner_id, validation_id))
    for field in result.get("financial_fields") or []:
        operations.append(_financial_field_op(field, document_id, batch_id, validation_id))
    financial_summary = result.get("document_financial_summary") or {}
    if financial_summary:
        operations.append(_statement_summary_op(financial_summary, result, document_id, validation_id))
        operations.append(_document_financial_summary_op(financial_summary, result, document_id, validation_id))
    for entity in result.get("validated_entities") or []:
        operations.append(_validated_entity_op(entity, document_id, validation_id))
    for reference in result.get("validated_references") or []:
        operations.append(_validated_reference_op(reference, document_id, validation_id))
    for line_item in result.get("validated_line_items") or []:
        operations.append(_line_item_op(line_item, document_id, validation_id))
    for installment in result.get("normalized_installments") or []:
        operations.append(_installment_op(installment, document_id, validation_id))
    for finding in result.get("findings") or []:
        operations.append(_finding_op(finding, document_id, validation_id))
    for review_item in result.get("review_items") or []:
        operations.append(_review_item_op(review_item, document_id, validation_id))

    return ValidationPersistencePlan(
        validation_id=validation_id,
        document_id=document_id,
        validation_result_id=result_id,
        operations=operations,
    )


def write_validation_payload_temp_file(result: dict[str, Any], temp_dir: str | Path | None = None) -> Path:
    """Write a validation result to a temporary handoff file for M9 persistence."""
    validation_id = _required_text(result, "validation_id")
    handoff_dir = _validation_handoff_dir(temp_dir)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_safe_token(validation_id)}-{uuid.uuid4().hex}.validation.json"
    handoff_file = handoff_dir / filename
    handoff_file.write_text(_json(result), encoding="utf-8")
    return handoff_file


def load_validation_payload_temp_file(handoff_file: str | Path) -> dict[str, Any]:
    """Load a validation result from a temporary handoff file."""
    payload = json.loads(Path(handoff_file).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("validation handoff payload must be a JSON object.")
    _required_text(payload, "validation_id")
    return payload


def build_validation_persistence_plan_from_temp_file(
    handoff_file: str | Path,
    **kwargs: Any,
) -> ValidationPersistencePlan:
    """Build a persistence plan from a temporary validation handoff file."""
    return build_validation_persistence_plan(load_validation_payload_temp_file(handoff_file), **kwargs)


def persist_validation_result(connection: Any, result: dict[str, Any], **kwargs: Any) -> ValidationPersistencePlan:
    """Persist a validation result through idempotent Azure SQL insert operations."""
    plan = build_validation_persistence_plan(result, **kwargs)
    cursor = connection.cursor()
    try:
        for operation in plan.operations:
            _execute_insert_if_missing(cursor, operation)
        _mark_promoted(cursor, plan.validation_result_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _close_cursor(cursor)
    return plan


def list_recent_uploaded_documents(connection: Any, *, limit: int = 25) -> list[UploadedDocumentSummary]:
    """Return recent uploaded documents saved through M9."""
    normalized_limit = max(1, min(int(limit), 100))
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
SELECT
    sd.document_id,
    sd.original_filename,
    sd.document_type,
    sd.status,
    sd.source_institution,
    sd.created_at_utc,
    sd.updated_at_utc,
    sd.uploaded_by_user_id,
    sd.storage_reference,
    sd.validation_result_id,
    COALESCE(tx.transaction_count, 0) AS transaction_count,
    COALESCE(ff.financial_field_count, 0) AS financial_field_count,
    COALESCE(ri.review_item_count, 0) AS review_item_count
FROM dbo.stats_documents AS sd
OUTER APPLY (
    SELECT COUNT(1) AS transaction_count
    FROM dbo.transactions AS t
    WHERE t.document_id = sd.document_id
) AS tx
OUTER APPLY (
    SELECT COUNT(1) AS financial_field_count
    FROM dbo.financial_fields AS f
    WHERE f.document_id = sd.document_id
) AS ff
OUTER APPLY (
    SELECT COUNT(1) AS review_item_count
    FROM dbo.review_items AS r
    WHERE r.document_id = sd.document_id
) AS ri
ORDER BY sd.created_at_utc DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY;
""",
            normalized_limit,
        )
        return [_uploaded_document_summary(row) for row in cursor.fetchall()]
    finally:
        _close_cursor(cursor)


def delete_uploaded_document_records(connection: Any, document_id: str) -> DeleteDocumentResult:
    """Delete one uploaded document and the M9 rows derived from it."""
    target_document_id = _text(document_id)
    if not target_document_id:
        raise ValueError("document_id is required.")

    cursor = connection.cursor()
    try:
        validation_result_id = _document_validation_result_id(cursor, target_document_id)
        deleted_counts: dict[str, int] = {}

        # Remove rows that can point at both document rows and transaction rows first.
        _execute_document_delete(
            cursor,
            deleted_counts,
            "financial_evidence_links",
            """
DELETE FROM dbo.financial_evidence_links
WHERE source_document_id = ?
   OR target_document_id = ?
   OR source_transaction_id IN (SELECT transaction_id FROM dbo.transactions WHERE document_id = ?)
   OR target_transaction_id IN (SELECT transaction_id FROM dbo.transactions WHERE document_id = ?);
""",
            target_document_id,
            target_document_id,
            target_document_id,
            target_document_id,
        )

        _execute_document_delete(
            cursor,
            deleted_counts,
            "review_items",
            "DELETE FROM dbo.review_items WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "findings",
            "DELETE FROM dbo.findings WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "installments",
            "DELETE FROM dbo.installments WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "line_items",
            "DELETE FROM dbo.line_items WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "validated_references",
            "DELETE FROM dbo.validated_references WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "validated_entities",
            "DELETE FROM dbo.validated_entities WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "document_sections",
            "DELETE FROM dbo.document_sections WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "document_financial_summaries",
            "DELETE FROM dbo.document_financial_summaries WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "statement_summaries",
            "DELETE FROM dbo.statement_summaries WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "financial_fields",
            "DELETE FROM dbo.financial_fields WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_statement(
            cursor,
            """
UPDATE dbo.transactions
SET duplicate_of_transaction_id = NULL
WHERE duplicate_of_transaction_id IN (SELECT transaction_id FROM dbo.transactions WHERE document_id = ?);
""",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "transactions",
            "DELETE FROM dbo.transactions WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "transaction_batches",
            "DELETE FROM dbo.transaction_batches WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "processing_runs",
            "DELETE FROM dbo.processing_runs WHERE document_id = ?;",
            target_document_id,
        )
        _execute_document_delete(
            cursor,
            deleted_counts,
            "stats_documents",
            "DELETE FROM dbo.stats_documents WHERE document_id = ?;",
            target_document_id,
        )

        if validation_result_id and not _validation_result_is_referenced(cursor, validation_result_id):
            _execute_document_delete(
                cursor,
                deleted_counts,
                "validation_results",
                "DELETE FROM dbo.validation_results WHERE validation_result_id = ?;",
                validation_result_id,
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _close_cursor(cursor)

    return DeleteDocumentResult(
        document_id=target_document_id,
        validation_result_id=validation_result_id,
        deleted_counts=deleted_counts,
    )


def persist_validation_result_from_temp_file(
    connection: Any,
    handoff_file: str | Path,
    **kwargs: Any,
) -> ValidationPersistencePlan:
    """Persist a validation handoff file and remove it only after a successful commit."""
    handoff_path = Path(handoff_file)
    plan = persist_validation_result(connection, load_validation_payload_temp_file(handoff_path), **kwargs)
    try:
        handoff_path.unlink()
    except FileNotFoundError:
        LOGGER.info("Validation handoff file was already removed: %s", handoff_path)
    except OSError:
        LOGGER.warning("Could not remove validation handoff file after successful commit: %s", handoff_path, exc_info=True)
    return plan


def persist_validation_result_with_temp_handoff(
    connection: Any,
    result: dict[str, Any],
    *,
    temp_dir: str | Path | None = None,
    **kwargs: Any,
) -> ValidationPersistencePlan:
    """Write a validation result to temp storage, persist it, then remove the file on success."""
    handoff_file = write_validation_payload_temp_file(result, temp_dir=temp_dir)
    return persist_validation_result_from_temp_file(connection, handoff_file, **kwargs)


def _document_section_op(section: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    return _op(
        "document_sections",
        {
            "document_section_id": _stable_id("section", validation_id, section.get("section_id")),
            "document_id": document_id,
            "source_section_id": _text(section.get("section_id")) or "unknown",
            "section_label": _text(section.get("section_label")) or "unknown",
            "page_number": _int_or_none(section.get("page_number")),
            "first_line_number": _int(section.get("first_line_number")),
            "last_line_number": _int(section.get("last_line_number")),
            "source_text_redacted": _text(section.get("source_text_redacted")) or "",
            "confidence": _confidence(section.get("confidence")),
            "reason_codes_json": _json(section.get("reason_codes") or []),
        },
    )


def _transaction_op(
    record: dict[str, Any],
    document_id: str,
    batch_id: str,
    owner_id: str | None,
    validation_id: str,
) -> SqlOperation:
    source = record.get("source") or {}
    transaction_id = _stable_id("transaction", validation_id, record.get("record_id"))
    duplicate_of = record.get("duplicate_of")
    return _op(
        "transactions",
        {
            "transaction_id": transaction_id,
            "transaction_batch_id": batch_id,
            "document_id": document_id,
            "source_candidate_id": _text(record.get("source_candidate_id")) or _text(record.get("record_id")),
            "transaction_date": _date_or_default(record.get("transaction_date")),
            "posted_date": _date_or_none(record.get("posted_date")),
            "description": _text(record.get("description")) or "",
            "normalized_description": _normalize_description(record.get("description")),
            "amount": _money(record.get("amount")),
            "currency": _currency(record.get("currency")),
            "direction": _text(record.get("direction")) or "unknown",
            "signed_amount": _money(record.get("signed_amount")),
            "confidence": _confidence(record.get("confidence")),
            "quality_status": _text(record.get("quality_status")) or "warning",
            "review_required": 1 if _review_required(record) else 0,
            "duplicate_of_transaction_id": _stable_id("transaction", validation_id, duplicate_of) if duplicate_of else None,
            "duplicate_key": _duplicate_key(owner_id, record),
            "source_page_number": _int_or_none(source.get("page_number")),
            "source_line_number": _int_or_none(source.get("line_number")),
            "source_section_id": _text(source.get("section_id")),
            "source_section_label": _text(source.get("section_label")),
            "source_text_redacted": _source_text(source),
            "source_ocr_confidence": _confidence(source.get("ocr_confidence")),
            "source_extraction_confidence": _confidence(source.get("extraction_confidence")),
            "reason_codes_json": _json(record.get("reason_codes") or []),
        },
    )


def _financial_field_op(field: dict[str, Any], document_id: str, batch_id: str, validation_id: str) -> SqlOperation:
    source = field.get("source") or {}
    return _op(
        "financial_fields",
        {
            "financial_field_id": _stable_id("financial-field", validation_id, field.get("field_name"), field.get("value")),
            "document_id": document_id,
            "transaction_batch_id": batch_id,
            "field_name": _text(field.get("field_name")) or "unknown",
            "field_label": _text(field.get("field_label")),
            "value_type": _text(field.get("value_type")) or "text",
            "value": _text(field.get("value")) or "",
            "currency": _text(field.get("currency")),
            "confidence": _confidence(field.get("confidence")),
            "quality_status": _text(field.get("quality_status")) or "warning",
            "source_page_number": _int_or_none(source.get("page_number")),
            "source_line_number": _int_or_none(source.get("line_number")),
            "source_section_id": _text(source.get("section_id")),
            "source_section_label": _text(source.get("section_label")),
            "source_text_redacted": _source_text(source),
            "source_ocr_confidence": _confidence(source.get("ocr_confidence")),
            "source_extraction_confidence": _confidence(source.get("extraction_confidence")),
            "reason_codes_json": _json(field.get("reason_codes") or []),
        },
    )


def _statement_summary_op(
    financial_summary: dict[str, Any],
    result: dict[str, Any],
    document_id: str,
    validation_id: str,
) -> SqlOperation:
    return _op(
        "statement_summaries",
        {
            "statement_summary_id": _stable_id("statement-summary", validation_id),
            "document_id": document_id,
            "statement_date": _date_value(financial_summary.get("statement_date")),
            "period_start_date": _date_value(financial_summary.get("period_start_date")),
            "period_end_date": _date_value(financial_summary.get("period_end_date")),
            "payment_due_date": _date_value(financial_summary.get("payment_due_date")),
            "minimum_amount_due": _money_text(financial_summary.get("minimum_amount_due")),
            "total_amount_due": _money_text(financial_summary.get("total_amount_due") or financial_summary.get("total_due")),
            "previous_balance": _money_text(financial_summary.get("previous_balance")),
            "payments_total": _money_text(financial_summary.get("payments_total") or financial_summary.get("payments_and_credits")),
            "purchases_total": _money_text(financial_summary.get("purchases_total")),
            "fees_total": _money_text(financial_summary.get("fees_total") or financial_summary.get("fees")),
            "interest_total": _money_text(financial_summary.get("interest_total") or financial_summary.get("interest")),
            "installment_balance": _money_text(financial_summary.get("installment_balance")),
            "outstanding_balance": _money_text(financial_summary.get("outstanding_balance")),
            "credit_limit": _money_text(financial_summary.get("credit_limit")),
            "available_credit": _money_text(financial_summary.get("available_credit")),
            "currency": _summary_currency(result),
            "confidence": _summary_confidence(result),
            "quality_status": _summary_quality_status(result),
        },
    )


def _document_financial_summary_op(
    financial_summary: dict[str, Any],
    result: dict[str, Any],
    document_id: str,
    validation_id: str,
) -> SqlOperation:
    return _op(
        "document_financial_summaries",
        {
            "document_financial_summary_id": _stable_id("document-financial-summary", validation_id),
            "document_id": document_id,
            "invoice_number": _text(financial_summary.get("invoice_number")),
            "issue_date": _date_value(financial_summary.get("issue_date") or financial_summary.get("statement_date")),
            "subtotal_amount": _money_text(financial_summary.get("subtotal_amount") or financial_summary.get("subtotal")),
            "tax_amount": _money_text(financial_summary.get("tax_amount") or financial_summary.get("total_gst") or financial_summary.get("gst_amount")),
            "total_amount": _money_text(
                financial_summary.get("total_amount")
                or financial_summary.get("receipt_total")
                or financial_summary.get("total_amount_due")
                or financial_summary.get("total_due")
            ),
            "paid_amount": _money_text(financial_summary.get("paid_amount")),
            "owing_amount": _money_text(financial_summary.get("owing_amount") or financial_summary.get("outstanding_balance")),
            "currency": _summary_currency(result),
            "payment_status": _text(financial_summary.get("payment_status")),
            "confidence": _summary_confidence(result),
            "quality_status": _summary_quality_status(result),
        },
    )


def _validated_entity_op(entity: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    source = entity.get("source") or {}
    return _op(
        "validated_entities",
        {
            "validated_entity_id": _stable_id("entity", validation_id, entity.get("entity_id")),
            "document_id": document_id,
            "source_entity_id": _text(entity.get("entity_id")) or "unknown",
            "entity_type": _text(entity.get("entity_type")) or "unknown",
            "value": _text(entity.get("value")) or "",
            "confidence": _confidence(entity.get("confidence")),
            "quality_status": _text(entity.get("quality_status")) or "warning",
            "reason_codes_json": _json(entity.get("reason_codes") or []),
            **_source_columns(source),
        },
    )


def _validated_reference_op(reference: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    source = reference.get("source") or {}
    return _op(
        "validated_references",
        {
            "validated_reference_id": _stable_id("reference", validation_id, reference.get("reference_id")),
            "document_id": document_id,
            "source_reference_id": _text(reference.get("reference_id")) or "unknown",
            "reference_type": _text(reference.get("reference_type")) or "unknown",
            "value": _text(reference.get("value")) or "",
            "masked": 1 if reference.get("masked") else 0,
            "confidence": _confidence(reference.get("confidence")),
            "quality_status": _text(reference.get("quality_status")) or "warning",
            "reason_codes_json": _json(reference.get("reason_codes") or []),
            **_source_columns(source),
        },
    )


def _line_item_op(line_item: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    source = line_item.get("source") or {}
    amount = _money(line_item.get("amount"))
    return _op(
        "line_items",
        {
            "line_item_id": _stable_id("line-item", validation_id, line_item.get("line_item_id")),
            "document_id": document_id,
            "source_line_item_id": _text(line_item.get("line_item_id")),
            "description": _text(line_item.get("description")) or "",
            "amount": amount,
            "currency": _currency(line_item.get("currency")) if amount is not None else _text(line_item.get("currency")),
            "line_amount": amount,
            "confidence": _confidence(line_item.get("confidence")),
            "quality_status": _text(line_item.get("quality_status")) or "warning",
            "reason_codes_json": _json(line_item.get("reason_codes") or []),
            **_source_columns(source),
        },
    )


def _installment_op(installment: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    source = installment.get("source") or {}
    return _op(
        "installments",
        {
            "installment_id": _stable_id("installment", validation_id, installment.get("installment_id")),
            "document_id": document_id,
            "source_installment_id": _text(installment.get("installment_id")) or "unknown",
            "purchase_date": _date_or_none(installment.get("purchase_date")),
            "posted_date": _date_or_none(installment.get("posted_date")),
            "description": _text(installment.get("description")) or "",
            "principal_amount": _money(installment.get("principal_amount")),
            "current_billing_amount": _money(installment.get("current_billing_amount")),
            "remaining_balance": _money(installment.get("remaining_balance")),
            "currency": _currency(installment.get("currency")),
            "term_text": _text(installment.get("term_text")),
            "confidence": _confidence(installment.get("confidence")),
            "quality_status": _text(installment.get("quality_status")) or "warning",
            "reason_codes_json": _json(installment.get("reason_codes") or []),
            **_source_columns(source),
        },
    )


def _finding_op(finding: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    return _op(
        "findings",
        {
            "finding_id": _stable_id("finding", validation_id, finding.get("record_id"), finding.get("code"), finding.get("message")),
            "document_id": document_id,
            "source_module": "Data Validation",
            "code": _text(finding.get("code")) or "UNKNOWN",
            "severity": _enum_value(finding.get("severity")) or "warning",
            "message": _text(finding.get("message")) or "",
            "status": "open",
        },
    )


def _review_item_op(review: dict[str, Any], document_id: str, validation_id: str) -> SqlOperation:
    source = review.get("source") or {}
    return _op(
        "review_items",
        {
            "review_item_id": _stable_id("review", validation_id, review.get("review_id")),
            "document_id": document_id,
            "source_review_id": _text(review.get("review_id")),
            "item_type": _text(review.get("item_type")) or "document",
            "severity": _text(review.get("severity")) or "warning",
            "title": _text(review.get("title")) or "Review item",
            "message": _text(review.get("message")) or "",
            "record_id": _text(review.get("record_id")),
            "field_name": _text(review.get("field_name")),
            "recommended_action": _text(review.get("recommended_action")) or "review",
            "status": "open",
            "source_page_number": _int_or_none(source.get("page_number")),
            "source_line_number": _int_or_none(source.get("line_number")),
            "source_section_id": _text(source.get("section_id")),
            "source_section_label": _text(source.get("section_label")),
            "source_text_redacted": _source_text(source),
            "source_ocr_confidence": _confidence(source.get("ocr_confidence")),
            "source_extraction_confidence": _confidence(source.get("extraction_confidence")),
            "reason_codes_json": _json(review.get("reason_codes") or []),
        },
    )


def _execute_insert_if_missing(cursor: Any, operation: SqlOperation) -> None:
    columns = list(operation.values)
    column_sql = ", ".join(f"[{column}]" for column in columns)
    source_value_sql = ", ".join(f"src.[{column}]" for column in columns)
    update_columns = [
        column
        for column in columns
        if column != operation.key_column and column not in {"created_at_utc", "created_at"}
    ]
    update_sql = ", ".join(_merge_update_assignment(operation.table, column) for column in update_columns)
    update_clause = f"WHEN MATCHED THEN UPDATE SET {update_sql}" if update_sql else ""
    source_sql = ", ".join(f"? AS [{column}]" for column in columns)
    sql = f"""
MERGE dbo.[{operation.table}] AS target
USING (SELECT {source_sql}) AS src
ON target.[{operation.key_column}] = src.[{operation.key_column}]
{update_clause}
WHEN NOT MATCHED THEN
    INSERT ({column_sql})
    VALUES ({source_value_sql});
"""
    params = list(operation.values.values())
    cursor.execute(sql, *params)


def _close_cursor(cursor: Any) -> None:
    try:
        cursor.close()
    except Exception:
        pass


def _merge_update_assignment(table: str, column: str) -> str:
    if table == "validation_results" and column in {"promotion_status", "promotion_error", "promoted_at_utc"}:
        return f"[{column}] = target.[{column}]"
    if table == "stats_documents" and column == "storage_reference":
        return "[storage_reference] = COALESCE(NULLIF(src.[storage_reference], ''), target.[storage_reference])"
    return f"[{column}] = src.[{column}]"


def _mark_promoted(cursor: Any, validation_result_id: str) -> None:
    cursor.execute(
        """
UPDATE dbo.validation_results
SET promotion_status = ?,
    promotion_error = CASE WHEN promotion_status = ? THEN promotion_error ELSE NULL END,
    promoted_at_utc = COALESCE(promoted_at_utc, SYSUTCDATETIME())
WHERE validation_result_id = ?;
""",
        "promoted",
        "promoted",
        validation_result_id,
    )


def _document_validation_result_id(cursor: Any, document_id: str) -> str | None:
    cursor.execute(
        "SELECT validation_result_id FROM dbo.stats_documents WHERE document_id = ?;",
        document_id,
    )
    row = cursor.fetchone()
    if not row:
        return None
    return row[0]


def _uploaded_document_summary(row: Any) -> UploadedDocumentSummary:
    return UploadedDocumentSummary(
        document_id=str(row.document_id),
        original_filename=str(row.original_filename),
        document_type=_text(row.document_type),
        status=str(row.status),
        source_institution=_text(row.source_institution),
        created_at_utc=_datetime_text(row.created_at_utc),
        updated_at_utc=_datetime_text(row.updated_at_utc),
        uploaded_by_user_id=_text(row.uploaded_by_user_id),
        storage_reference=_text(row.storage_reference),
        validation_result_id=_text(row.validation_result_id),
        transaction_count=int(row.transaction_count or 0),
        financial_field_count=int(row.financial_field_count or 0),
        review_item_count=int(row.review_item_count or 0),
    )


def _validation_result_is_referenced(cursor: Any, validation_result_id: str) -> bool:
    cursor.execute(
        "SELECT COUNT(1) FROM dbo.stats_documents WHERE validation_result_id = ?;",
        validation_result_id,
    )
    row = cursor.fetchone()
    return bool(row and int(row[0] or 0))


def _execute_document_delete(
    cursor: Any,
    deleted_counts: dict[str, int],
    table: str,
    sql: str,
    *params: Any,
) -> None:
    cursor.execute(sql, *params)
    rowcount = int(cursor.rowcount or 0) if getattr(cursor, "rowcount", -1) and cursor.rowcount > 0 else 0
    deleted_counts[table] = deleted_counts.get(table, 0) + rowcount


def _execute_document_statement(cursor: Any, sql: str, *params: Any) -> None:
    cursor.execute(sql, *params)


def _op(table: str, values: dict[str, Any]) -> SqlOperation:
    key_column = TABLE_PRIMARY_KEYS[table]
    return SqlOperation(table=table, key_column=key_column, values={key: value for key, value in values.items()})


def _source_columns(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_page_number": _int_or_none(source.get("page_number")),
        "source_line_number": _int_or_none(source.get("line_number")),
        "source_section_id": _text(source.get("section_id")),
        "source_section_label": _text(source.get("section_label")),
        "source_text_redacted": _source_text(source),
        "source_ocr_confidence": _confidence(source.get("ocr_confidence")),
        "source_extraction_confidence": _confidence(source.get("extraction_confidence")),
    }


def _stable_id(*parts: Any) -> str:
    material = "|".join(_text(part) or "" for part in parts)
    return str(uuid.uuid5(NAMESPACE, material))


def _validation_handoff_dir(temp_dir: str | Path | None = None) -> Path:
    if temp_dir:
        return Path(temp_dir)
    configured = os.environ.get(VALIDATION_HANDOFF_DIR_ENV)
    if configured:
        return Path(configured)
    return Path(tempfile.gettempdir()) / "stats-m9-handoff"


def _safe_token(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", _text(value) or "validation-payload").strip("-") or "validation-payload"


def _required_text(result: dict[str, Any], key: str) -> str:
    value = _text(result.get(key))
    if not value:
        raise ValueError(f"validation result is missing required field: {key}")
    return value


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    text = str(value).strip()
    return text or None


def _datetime_text(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return _text(value)


def _enum_value(value: Any) -> str:
    return _text(value) or ""


def _int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _int_or_none(value: Any) -> int | None:
    return None if value is None else int(value)


def _money(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _money_text(value: Any) -> Decimal | None:
    text = _text(value)
    if not text:
        return None
    normalized = re.sub(r"[^0-9.,-]+", "", text).replace(",", "")
    if not normalized or normalized in {"-", ".", "-."}:
        return None
    return _money(normalized)


def _confidence(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _json(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Cannot JSON serialize {type(value).__name__}")


def _currency(value: Any) -> str:
    return (_text(value) or DEFAULT_CURRENCY).upper()


def _date_or_none(value: Any) -> str | None:
    return _text(value)


def _date_or_default(value: Any) -> str:
    return _text(value) or "1900-01-01"


def _date_value(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _normalize_description(value: Any) -> str:
    return re.sub(r"\s+", " ", (_text(value) or "")).strip().lower()


def _source_text(source: dict[str, Any]) -> str | None:
    return _text(source.get("source_text_redacted")) or _text(source.get("text"))


def _review_required(record: dict[str, Any]) -> bool:
    return bool(record.get("duplicate_of")) or _text(record.get("quality_status")) != "valid"


def _duplicate_key(owner_id: str | None, record: dict[str, Any]) -> str:
    raw = "|".join(
        [
            owner_id or "",
            _text(record.get("transaction_date")) or "",
            _normalize_description(record.get("description")),
            str(_money(record.get("signed_amount")) or _money(record.get("amount")) or ""),
            _currency(record.get("currency")),
            _text(record.get("direction")) or "unknown",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _document_fingerprint(result: dict[str, Any]) -> str:
    document = result.get("document") or {}
    summary = result.get("document_financial_summary") or {}
    parts: list[str] = [
        _text(result.get("document_type")) or "",
        _text(document.get("sha256")) or "",
        _first_entity_value(result, "institution") or "",
        _first_entity_value(result, "merchant") or "",
        _first_entity_value(result, "counterparty") or "",
    ]
    for field_name in [
        "statement_date",
        "period_start_date",
        "period_end_date",
        "payment_due_date",
        "issue_date",
        "total_amount",
        "receipt_total",
        "total_amount_due",
        "total_due",
        "paid_amount",
        "owing_amount",
        "currency",
    ]:
        parts.append(_text(summary.get(field_name)) or "")
    for reference in (result.get("validated_references") or [])[:6]:
        parts.append(_text(reference.get("reference_type")) or "")
        parts.append(_text(reference.get("value")) or "")
    for record in (result.get("normalized_records") or [])[:5]:
        parts.extend(
            [
                _text(record.get("transaction_date")) or "",
                _normalize_description(record.get("description")),
                str(_money(record.get("signed_amount")) or _money(record.get("amount")) or ""),
                _currency(record.get("currency")),
                _text(record.get("direction")) or "unknown",
            ]
        )
    material = "|".join(re.sub(r"\s+", " ", part.lower()).strip() for part in parts if part)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _first_entity_value(result: dict[str, Any], entity_type: str) -> str | None:
    for entity in result.get("validated_entities") or []:
        if (_text(entity.get("entity_type")) or "").lower() == entity_type:
            return _text(entity.get("value"))
    return None


def _document_status(summary: dict[str, Any], result: dict[str, Any]) -> str:
    review_status = _text(summary.get("document_review_status"))
    if review_status in {"blocked", "needs_review"}:
        return "needs_review"
    status = _enum_value(result.get("status"))
    if status == "failed":
        return "failed"
    return "validated"


def _document_quality_status(result: dict[str, Any]) -> str | None:
    if result.get("review_items"):
        return "needs_review"
    if result.get("findings"):
        return "warning"
    return "valid"


def _summary_currency(result: dict[str, Any]) -> str:
    for field in result.get("financial_fields") or []:
        currency = _text(field.get("currency"))
        if currency:
            return _currency(currency)
    return DEFAULT_CURRENCY


def _summary_confidence(result: dict[str, Any]) -> Decimal | None:
    values = [
        Decimal(str(field.get("confidence")))
        for field in result.get("financial_fields") or []
        if field.get("confidence") is not None
    ]
    if not values:
        return None
    average = sum(values) / Decimal(len(values))
    return _confidence(average)


def _summary_quality_status(result: dict[str, Any]) -> str:
    statuses = {_text(field.get("quality_status")) for field in result.get("financial_fields") or []}
    if "invalid" in statuses:
        return "invalid"
    if "warning" in statuses:
        return "warning"
    return "valid"


def _batch_status(summary: dict[str, Any], result: dict[str, Any]) -> str:
    if _enum_value(result.get("status")) == "failed":
        return "failed"
    if _int(summary.get("invalid_record_count")) or _int(summary.get("review_item_count")):
        return "needs_review"
    return "saved"


def table_counts(operations: Iterable[SqlOperation]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for operation in operations:
        counts[operation.table] = counts.get(operation.table, 0) + 1
    return counts


def _utc_now_token() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
