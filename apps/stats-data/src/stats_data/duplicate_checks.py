"""M9 - Stats Data and Persistence Start
Provides pre-save duplicate checks against stored Stats data.
M9 End"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from stats_data.validation_persistence import (
    SqlOperation,
    _close_cursor,
    _document_fingerprint,
    _execute_insert_if_missing,
    _json,
    _op,
    _stable_id,
    _text,
    build_validation_persistence_plan,
)


DOCUMENT_MATCH_COLUMNS = {"sha256", "document_fingerprint"}


@dataclass(frozen=True)
class DuplicateCheckResult:
    duplicate_check_id: str
    validation_id: str
    document_id: str
    status: str
    summary: dict[str, int]
    document_results: list[dict[str, Any]]
    transaction_results: list[dict[str, Any]]


def check_validation_duplicates(
    connection: Any,
    result: dict[str, Any],
    *,
    uploaded_by_user_id: str | None = None,
    saved_by_user_id: str | None = None,
    storage_reference: str | None = None,
) -> DuplicateCheckResult:
    """Check one reviewed validation result against persisted documents and transactions."""
    plan = build_validation_persistence_plan(
        result,
        uploaded_by_user_id=uploaded_by_user_id,
        saved_by_user_id=saved_by_user_id,
        storage_reference=storage_reference,
    )
    cursor = connection.cursor()
    try:
        # Persist the validation/document shell so duplicate-check results have a durable parent.
        for operation in _document_shell_operations(plan):
            _execute_insert_if_missing(cursor, operation)

        document_result_rows = _document_duplicate_results(cursor, result, plan, uploaded_by_user_id)
        transaction_result_rows = _transaction_duplicate_results(cursor, plan, saved_by_user_id or uploaded_by_user_id)
        summary = _summary(plan, document_result_rows, transaction_result_rows)
        status = _status(summary)
        duplicate_check_id = _stable_id("duplicate-check", plan.validation_id)

        batch = _duplicate_check_batch_operation(
            duplicate_check_id=duplicate_check_id,
            validation_id=plan.validation_id,
            document_id=plan.document_id,
            uploaded_by_user_id=uploaded_by_user_id,
            saved_by_user_id=saved_by_user_id,
            status=status,
            summary=summary,
        )
        _execute_insert_if_missing(cursor, batch)

        for index, row in enumerate([*document_result_rows, *transaction_result_rows], start=1):
            _execute_insert_if_missing(
                cursor,
                _duplicate_check_result_operation(
                    duplicate_check_id=duplicate_check_id,
                    document_id=plan.document_id,
                    index=index,
                    row=row,
                ),
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _close_cursor(cursor)

    return DuplicateCheckResult(
        duplicate_check_id=duplicate_check_id,
        validation_id=plan.validation_id,
        document_id=plan.document_id,
        status=status,
        summary=summary,
        document_results=document_result_rows,
        transaction_results=transaction_result_rows,
    )


def _document_shell_operations(plan) -> list[SqlOperation]:
    return [operation for operation in plan.operations if operation.table in {"validation_results", "stats_documents"}]


def _document_duplicate_results(
    cursor: Any,
    result: dict[str, Any],
    plan,
    uploaded_by_user_id: str | None,
) -> list[dict[str, Any]]:
    document = result.get("document") or {}
    sha256 = _text(document.get("sha256"))
    fingerprint = _document_fingerprint(result)
    rows: list[dict[str, Any]] = []

    if sha256:
        for match in _fetch_matching_documents(cursor, "sha256", sha256, uploaded_by_user_id, plan.document_id):
            rows.append(
                _result_row(
                    result_scope="document",
                    match_type="exact_file_duplicate",
                    match_status="blocked",
                    matched_document_id=match["document_id"],
                    confidence=Decimal("1.0"),
                    reason_codes=["MATCHED_FILE_SHA256"],
                    message="This file was already uploaded.",
                )
            )

    if _has_document_fingerprint_evidence(result, fingerprint):
        for match in _fetch_matching_documents(cursor, "document_fingerprint", fingerprint, uploaded_by_user_id, plan.document_id):
            rows.append(
                _result_row(
                    result_scope="document",
                    match_type="possible_same_document",
                    match_status="needs_review",
                    matched_document_id=match["document_id"],
                    confidence=Decimal("0.88"),
                    reason_codes=["MATCHED_DOCUMENT_FINGERPRINT"],
                    message="This document looks similar to one already saved.",
                )
            )

    return rows


def _fetch_matching_documents(
    cursor: Any,
    column: str,
    value: str,
    owner_id: str | None,
    current_document_id: str,
) -> list[dict[str, Any]]:
    if not value:
        return []
    if column not in DOCUMENT_MATCH_COLUMNS:
        raise ValueError(f"unsupported document duplicate match column: {column}")
    cursor.execute(
        f"""
SELECT document_id, original_filename
FROM dbo.stats_documents
WHERE [{column}] = ?
  AND document_id <> ?
  AND (? IS NULL OR uploaded_by_user_id = ?)
ORDER BY created_at_utc DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY;
""",
        value,
        current_document_id,
        owner_id,
        owner_id,
        5,
    )
    return [_row_dict(row, ["document_id", "original_filename"]) for row in cursor.fetchall()]


def _transaction_duplicate_results(cursor: Any, plan, owner_id: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_keys: dict[str, str] = {}
    transaction_operations = [operation for operation in plan.operations if operation.table == "transactions"]
    exact_matches = _fetch_transactions_by_duplicate_keys(
        cursor,
        [_text(operation.values.get("duplicate_key")) for operation in transaction_operations],
    )
    for operation in transaction_operations:
        values = operation.values
        record_id = _text(values.get("source_candidate_id")) or _text(values.get("transaction_id"))
        duplicate_key = _text(values.get("duplicate_key")) or ""

        if duplicate_key and duplicate_key in seen_keys:
            rows.append(
                _result_row(
                    result_scope="transaction",
                    match_type="within_batch_duplicate",
                    match_status="needs_review",
                    record_id=record_id,
                    confidence=Decimal("1.0"),
                    reason_codes=["MATCHED_WITHIN_BATCH_DUPLICATE_KEY"],
                    message="This transaction duplicates another row in the current upload.",
                )
            )
            continue
        if duplicate_key:
            seen_keys[duplicate_key] = record_id or ""

        exact_match = exact_matches.get(duplicate_key) if duplicate_key else None
        if exact_match:
            rows.append(
                _result_row(
                    result_scope="transaction",
                    match_type="exact_transaction_duplicate",
                    match_status="blocked",
                    record_id=record_id,
                    matched_document_id=exact_match.get("document_id"),
                    matched_transaction_id=exact_match.get("transaction_id"),
                    confidence=Decimal("1.0"),
                    reason_codes=["MATCHED_TRANSACTION_DUPLICATE_KEY"],
                    message="This transaction already exists.",
                )
            )
            continue

        for possible_match in _fetch_possible_transaction_matches(cursor, values, owner_id, duplicate_key):
            rows.append(
                _result_row(
                    result_scope="transaction",
                    match_type="possible_transaction_duplicate",
                    match_status="needs_review",
                    record_id=record_id,
                    matched_document_id=possible_match.get("document_id"),
                    matched_transaction_id=possible_match.get("transaction_id"),
                    confidence=Decimal("0.72"),
                    reason_codes=["MATCHED_DATE_AMOUNT_CURRENCY_DIRECTION"],
                    message="This transaction has the same date, amount, currency, and direction as a saved transaction.",
                )
            )
            break

    return rows


def _fetch_transactions_by_duplicate_keys(cursor: Any, duplicate_keys: list[str | None]) -> dict[str, dict[str, Any]]:
    keys = sorted({_text(key) for key in duplicate_keys if _text(key)})
    if not keys:
        return {}
    placeholders = ", ".join("?" for _ in keys)
    cursor.execute(
        f"""
SELECT duplicate_key, transaction_id, document_id
FROM dbo.transactions
WHERE duplicate_key IN ({placeholders})
ORDER BY created_at_utc DESC
""",
        *keys,
    )
    matches: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        row_data = _row_dict(row, ["duplicate_key", "transaction_id", "document_id"])
        key = _text(row_data.get("duplicate_key"))
        if key and key not in matches:
            matches[key] = row_data
    return matches


def _fetch_possible_transaction_matches(
    cursor: Any,
    values: dict[str, Any],
    owner_id: str | None,
    duplicate_key: str,
) -> list[dict[str, Any]]:
    cursor.execute(
        """
SELECT t.transaction_id, t.document_id, t.description
FROM dbo.transactions AS t
INNER JOIN dbo.transaction_batches AS b
    ON b.transaction_batch_id = t.transaction_batch_id
WHERE t.transaction_date = ?
  AND t.amount = ?
  AND t.currency = ?
  AND t.direction = ?
  AND t.duplicate_key <> ?
  AND (? IS NULL OR b.saved_by_user_id = ?)
ORDER BY t.created_at_utc DESC
OFFSET 0 ROWS FETCH NEXT ? ROWS ONLY;
""",
        values.get("transaction_date"),
        values.get("amount"),
        values.get("currency"),
        values.get("direction"),
        duplicate_key,
        owner_id,
        owner_id,
        5,
    )
    return [_row_dict(row, ["transaction_id", "document_id", "description"]) for row in cursor.fetchall()]


def _duplicate_check_batch_operation(
    *,
    duplicate_check_id: str,
    validation_id: str,
    document_id: str,
    uploaded_by_user_id: str | None,
    saved_by_user_id: str | None,
    status: str,
    summary: dict[str, int],
) -> SqlOperation:
    return _op(
        "duplicate_check_batches",
        {
            "duplicate_check_id": duplicate_check_id,
            "validation_id": validation_id,
            "document_id": document_id,
            "uploaded_by_user_id": uploaded_by_user_id,
            "saved_by_user_id": saved_by_user_id,
            "status": status,
            "total_record_count": summary["total_checked"],
            "exact_file_duplicate_count": summary["exact_file_duplicates"],
            "possible_document_duplicate_count": summary["possible_document_duplicates"],
            "within_batch_duplicate_count": summary["within_batch_duplicates"],
            "exact_transaction_duplicate_count": summary["exact_transaction_duplicates"],
            "possible_transaction_duplicate_count": summary["possible_transaction_duplicates"],
            "ready_to_save_count": summary["ready_to_save"],
            "summary_json": _json(summary),
        },
    )


def _duplicate_check_result_operation(
    *,
    duplicate_check_id: str,
    document_id: str,
    index: int,
    row: dict[str, Any],
) -> SqlOperation:
    result_id = _stable_id(
        "duplicate-check-result",
        duplicate_check_id,
        _text(row.get("result_scope")),
        _text(row.get("match_type")),
        _text(row.get("record_id")),
        _text(row.get("matched_document_id")),
        _text(row.get("matched_transaction_id")),
        _json(row.get("reason_codes") or []),
    )
    return _op(
        "duplicate_check_results",
        {
            "duplicate_check_result_id": result_id,
            "duplicate_check_id": duplicate_check_id,
            "document_id": document_id,
            "record_id": _text(row.get("record_id")),
            "result_scope": row["result_scope"],
            "match_type": row["match_type"],
            "match_status": row["match_status"],
            "matched_document_id": _text(row.get("matched_document_id")),
            "matched_transaction_id": _text(row.get("matched_transaction_id")),
            "confidence": row.get("confidence"),
            "reason_codes_json": _json(row.get("reason_codes") or []),
            "message": _text(row.get("message")),
        },
    )


def _summary(plan, document_rows: list[dict[str, Any]], transaction_rows: list[dict[str, Any]]) -> dict[str, int]:
    total_checked = len([operation for operation in plan.operations if operation.table == "transactions"])
    exact_transaction_duplicates = _count(transaction_rows, "exact_transaction_duplicate")
    possible_transaction_duplicates = _count(transaction_rows, "possible_transaction_duplicate")
    within_batch_duplicates = _count(transaction_rows, "within_batch_duplicate")
    blocked_or_review = exact_transaction_duplicates + possible_transaction_duplicates + within_batch_duplicates
    return {
        "total_checked": total_checked,
        "exact_file_duplicates": _count(document_rows, "exact_file_duplicate"),
        "possible_document_duplicates": _count(document_rows, "possible_same_document"),
        "within_batch_duplicates": within_batch_duplicates,
        "exact_transaction_duplicates": exact_transaction_duplicates,
        "possible_transaction_duplicates": possible_transaction_duplicates,
        "ready_to_save": max(total_checked - blocked_or_review, 0),
    }


def _status(summary: dict[str, int]) -> str:
    if summary["exact_file_duplicates"] or summary["exact_transaction_duplicates"]:
        return "blocked"
    if (
        summary["possible_document_duplicates"]
        or summary["within_batch_duplicates"]
        or summary["possible_transaction_duplicates"]
    ):
        return "needs_review"
    return "ready"


def _count(rows: list[dict[str, Any]], match_type: str) -> int:
    return sum(1 for row in rows if row.get("match_type") == match_type)


def _result_row(
    *,
    result_scope: str,
    match_type: str,
    match_status: str,
    record_id: str | None = None,
    matched_document_id: str | None = None,
    matched_transaction_id: str | None = None,
    confidence: Decimal | None = None,
    reason_codes: list[str] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "result_scope": result_scope,
        "match_type": match_type,
        "match_status": match_status,
        "record_id": record_id,
        "matched_document_id": matched_document_id,
        "matched_transaction_id": matched_transaction_id,
        "confidence": confidence,
        "reason_codes": reason_codes or [],
        "message": message,
    }


def _row_dict(row: Any, columns: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for index, column in enumerate(columns):
        if hasattr(row, column):
            result[column] = getattr(row, column)
        elif hasattr(row, "__getitem__"):
            try:
                result[column] = row[column]
            except (TypeError, KeyError, IndexError):
                result[column] = row[index]
        else:
            result[column] = None
    return result


def _has_document_fingerprint_evidence(result: dict[str, Any], fingerprint: str) -> bool:
    if not fingerprint:
        return False
    document = result.get("document") or {}
    summary = result.get("document_financial_summary") or {}
    evidence_values = [
        document.get("sha256"),
        result.get("validated_entities"),
        result.get("validated_references"),
        result.get("normalized_records"),
        [value for value in summary.values() if _text(value)],
    ]
    return any(bool(value) for value in evidence_values)
