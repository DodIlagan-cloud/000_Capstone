"""M9 - Stats Data reporting query builders and read-model access Start

M11 consumes these user-scoped read models for the native dashboard, documents
provenance, transactions drilldown, findings, and review queues. Query text and
column identifiers are fixed in code; every user-supplied value is bound as a
parameter, and every read is scoped to the authenticated user's documents.

The pure builder functions here take no database connection so they can be unit
tested without Azure SQL. The ``fetch_*`` helpers execute them against a live
connection using the same open/close pattern as ``validation_persistence``.
M9 End"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# --- Column projections -----------------------------------------------------
# Fixed identifier lists. These are never taken from request input, so building
# SELECT clauses from them cannot introduce SQL injection.

_TRANSACTION_COLUMNS = (
    "transaction_id",
    "document_id",
    "transaction_batch_id",
    "transaction_date",
    "posted_date",
    "description",
    "normalized_description",
    "amount",
    "currency",
    "direction",
    "signed_amount",
    "expense_amount",
    "credit_amount",
    "source_institution",
    "expense_contributor",
    "merchant_or_counterparty",
    "category",
    "transaction_type",
    "transaction_subtype",
    "spending_category",
    "spending_subcategory",
    "classification_source",
    "classification_review_required",
    "payment_method",
    "masked_account_or_card",
    "confidence",
    "quality_status",
    "review_required",
    "source_page_number",
    "source_line_number",
    "source_text_redacted",
    "original_filename",
    "document_type",
    "document_status",
    "ocr_quality_status",
    "created_at_utc",
    "updated_at_utc",
)

_REVIEW_ITEM_COLUMNS = (
    "review_item_id",
    "document_id",
    "transaction_id",
    "original_filename",
    "document_type",
    "source_type",
    "source_institution",
    "item_type",
    "severity",
    "title",
    "message",
    "field_name",
    "recommended_action",
    "status",
    "source_page_number",
    "source_line_number",
    "source_text_redacted",
    "transaction_description",
    "transaction_amount",
    "transaction_currency",
    "transaction_direction",
    "affected_expense_amount",
    "spending_category",
    "transaction_type",
    "created_at_utc",
    "resolved_at_utc",
)

_FINDING_COLUMNS = (
    "finding_id",
    "document_id",
    "transaction_id",
    "processing_run_id",
    "original_filename",
    "document_type",
    "source_type",
    "source_module",
    "code",
    "severity",
    "message",
    "status",
    "transaction_description",
    "transaction_amount",
    "transaction_currency",
    "affected_expense_amount",
    "created_at_utc",
    "resolved_at_utc",
)

_DOCUMENT_PROVENANCE_COLUMNS = (
    "document_id",
    "original_filename",
    "source_type",
    "document_type",
    "source_institution",
    "status",
    "ocr_quality_status",
    "redaction_applied",
    "transaction_count",
    "financial_field_count",
    "review_item_count",
    "created_at_utc",
    "updated_at_utc",
)

_MAX_PAGE_SIZE = 500
_DEFAULT_PAGE_SIZE = 100


def _clamp_limit(limit: int | None) -> int:
    if not limit or limit < 1:
        return _DEFAULT_PAGE_SIZE
    return min(int(limit), _MAX_PAGE_SIZE)


def _clamp_offset(offset: int | None) -> int:
    if not offset or offset < 0:
        return 0
    return int(offset)


def _projection(columns: tuple[str, ...]) -> str:
    return ", ".join(columns)


# --- Transactions -----------------------------------------------------------


@dataclass
class TransactionFilters:
    """Optional filters for the transaction drilldown, per the M11 spec."""

    currency: str | None = None
    direction: str | None = None
    transaction_type: str | None = None
    transaction_subtype: str | None = None
    spending_category: str | None = None
    spending_subcategory: str | None = None
    merchant: str | None = None
    source_institution: str | None = None
    payment_method: str | None = None
    quality_status: str | None = None
    classification_source: str | None = None
    review_required: bool | None = None
    date_from: str | None = None
    date_to: str | None = None
    limit: int | None = None
    offset: int | None = None


# Maps a filter attribute to the exact read-model column it constrains.
_TRANSACTION_EQ_COLUMNS = (
    ("currency", "currency"),
    ("direction", "direction"),
    ("transaction_type", "transaction_type"),
    ("transaction_subtype", "transaction_subtype"),
    ("spending_category", "spending_category"),
    ("spending_subcategory", "spending_subcategory"),
    ("source_institution", "source_institution"),
    ("payment_method", "payment_method"),
    ("quality_status", "quality_status"),
    ("classification_source", "classification_source"),
)


def build_transactions_query(user_id: str, filters: TransactionFilters, include_all: bool = False) -> tuple[str, list[Any]]:
    """Build a user-scoped, parameterized transactions query and its bind params."""

    where: list[str] = ["(uploaded_by_user_id = ? OR ? = 1)"]
    params: list[Any] = [user_id, 1 if include_all else 0]

    for attr, column in _TRANSACTION_EQ_COLUMNS:
        value = getattr(filters, attr)
        if value is not None and value != "":
            where.append(f"{column} = ?")
            params.append(value)

    if filters.merchant:
        where.append("(merchant_or_counterparty LIKE ? OR expense_contributor LIKE ?)")
        like = f"%{filters.merchant}%"
        params.extend([like, like])

    if filters.review_required is not None:
        where.append("review_required = ?")
        params.append(1 if filters.review_required else 0)

    if filters.date_from:
        where.append("transaction_date >= ?")
        params.append(filters.date_from)

    if filters.date_to:
        where.append("transaction_date <= ?")
        params.append(filters.date_to)

    limit = _clamp_limit(filters.limit)
    offset = _clamp_offset(filters.offset)

    sql = (
        f"SELECT {_projection(_TRANSACTION_COLUMNS)} "
        "FROM dbo.vw_reporting_transactions "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY transaction_date DESC, transaction_id DESC "
        "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    )
    params.extend([offset, limit])
    return sql, params


# --- Documents provenance summary ------------------------------------------


def build_document_provenance_query(user_id: str, include_all: bool = False) -> tuple[str, list[Any]]:
    """Rows backing the Documents provenance summaries and table, user-scoped."""

    sql = (
        f"SELECT {_projection(_DOCUMENT_PROVENANCE_COLUMNS)} "
        "FROM dbo.vw_reporting_document_provenance "
        "WHERE (uploaded_by_user_id = ? OR ? = 1) "
        "ORDER BY created_at_utc DESC, document_id DESC"
    )
    return sql, [user_id, 1 if include_all else 0]


def build_document_detail_query(user_id: str, document_id: str, include_all: bool = False) -> tuple[str, list[Any]]:
    """Single document drilldown, scoped so a user cannot read another's document."""

    sql = (
        f"SELECT {_projection(_DOCUMENT_PROVENANCE_COLUMNS)} "
        "FROM dbo.vw_reporting_document_provenance "
        "WHERE (uploaded_by_user_id = ? OR ? = 1) AND document_id = ?"
    )
    return sql, [user_id, 1 if include_all else 0, document_id]


def summarize_document_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the spec's provenance rollups from already user-scoped rows.

    Kept as a pure function over mapped rows so it is unit testable without a
    database. Counts documents by type/source/status/quality and totals the
    represented transaction and review rows.
    """

    def _bucket(key: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in rows:
            label = row.get(key) or "unknown"
            counts[label] = counts.get(label, 0) + 1
        return counts

    latest = None
    for row in rows:
        created = row.get("created_at_utc")
        if created is not None and (latest is None or str(created) > str(latest)):
            latest = created

    return {
        "saved_documents": len(rows),
        "by_document_type": _bucket("document_type"),
        "by_source_type": _bucket("source_type"),
        "by_source_institution": _bucket("source_institution"),
        "by_status": _bucket("status"),
        "by_ocr_quality_status": _bucket("ocr_quality_status"),
        "total_transaction_rows": sum(int(r.get("transaction_count") or 0) for r in rows),
        "total_review_items": sum(int(r.get("review_item_count") or 0) for r in rows),
        "latest_saved_document_utc": latest,
    }


# --- Review items -----------------------------------------------------------


def build_review_items_query(
    user_id: str,
    status: str | None = None,
    severity: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    include_all: bool = False,
) -> tuple[str, list[Any]]:
    """High-impact review queue, user-scoped, ordered by affected reporting amount."""

    where: list[str] = ["(uploaded_by_user_id = ? OR ? = 1)"]
    params: list[Any] = [user_id, 1 if include_all else 0]

    if status:
        where.append("status = ?")
        params.append(status)
    if severity:
        where.append("severity = ?")
        params.append(severity)

    limit_value = _clamp_limit(limit)
    offset_value = _clamp_offset(offset)

    sql = (
        f"SELECT {_projection(_REVIEW_ITEM_COLUMNS)} "
        "FROM dbo.vw_reporting_review_items "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY affected_expense_amount DESC, created_at_utc DESC, review_item_id DESC "
        "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    )
    params.extend([offset_value, limit_value])
    return sql, params


# --- Findings ---------------------------------------------------------------


def build_findings_query(
    user_id: str,
    status: str | None = None,
    severity: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    include_all: bool = False,
) -> tuple[str, list[Any]]:
    """Open system/module findings, user-scoped, ordered by affected amount."""

    where: list[str] = ["(uploaded_by_user_id = ? OR ? = 1)"]
    params: list[Any] = [user_id, 1 if include_all else 0]

    if status:
        where.append("status = ?")
        params.append(status)
    if severity:
        where.append("severity = ?")
        params.append(severity)

    limit_value = _clamp_limit(limit)
    offset_value = _clamp_offset(offset)

    sql = (
        f"SELECT {_projection(_FINDING_COLUMNS)} "
        "FROM dbo.vw_reporting_findings "
        f"WHERE {' AND '.join(where)} "
        "ORDER BY affected_expense_amount DESC, created_at_utc DESC, finding_id DESC "
        "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    )
    params.extend([offset_value, limit_value])
    return sql, params


# --- Row mapping + execution ------------------------------------------------


def rows_to_dicts(cursor: Any) -> list[dict[str, Any]]:
    """Map a pyodbc cursor result set to plain dicts using its column names."""

    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _fetch(connection: Any, sql: str, params: list[Any]) -> list[dict[str, Any]]:
    cursor = connection.cursor()
    try:
        cursor.execute(sql, params)
        return rows_to_dicts(cursor)
    finally:
        cursor.close()


def fetch_transactions(connection: Any, user_id: str, filters: TransactionFilters, include_all: bool = False) -> list[dict[str, Any]]:
    sql, params = build_transactions_query(user_id, filters, include_all=include_all)
    return _fetch(connection, sql, params)


def fetch_document_provenance(connection: Any, user_id: str, include_all: bool = False) -> list[dict[str, Any]]:
    sql, params = build_document_provenance_query(user_id, include_all=include_all)
    return _fetch(connection, sql, params)


def fetch_document_detail(connection: Any, user_id: str, document_id: str, include_all: bool = False) -> dict[str, Any] | None:
    sql, params = build_document_detail_query(user_id, document_id, include_all=include_all)
    rows = _fetch(connection, sql, params)
    return rows[0] if rows else None


def fetch_review_items(connection: Any, user_id: str, **kwargs: Any) -> list[dict[str, Any]]:
    sql, params = build_review_items_query(user_id, **kwargs)
    return _fetch(connection, sql, params)


def fetch_findings(connection: Any, user_id: str, **kwargs: Any) -> list[dict[str, Any]]:
    sql, params = build_findings_query(user_id, **kwargs)
    return _fetch(connection, sql, params)


# M11 End
