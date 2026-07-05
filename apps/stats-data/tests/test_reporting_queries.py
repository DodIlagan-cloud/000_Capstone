"""M9/M11 - Unit tests for reporting query builders.

Pure-Python tests: no Azure SQL or pyodbc required. They assert user scoping,
the admin bypass, parameter binding, filter mapping, and paging bounds for the
M11 read models. Every scoped query uses "(uploaded_by_user_id = ? OR ? = 1)":
the second bind is 0 for ordinary users (scoped) and 1 for admins (unscoped,
per the spec's role-aware cross-user visibility).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stats_data.reporting_queries import (  # noqa: E402
    TransactionFilters,
    build_document_detail_query,
    build_document_provenance_query,
    build_findings_query,
    build_review_items_query,
    build_transactions_query,
    summarize_document_rows,
)


def test_transactions_query_is_user_scoped_first_param():
    sql, params = build_transactions_query("user-123", TransactionFilters())
    assert "(uploaded_by_user_id = ? OR ? = 1)" in sql
    assert params[0] == "user-123"
    assert params[1] == 0
    assert params[-2] == 0
    assert params[-1] == 100
    assert "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY" in sql


def test_transactions_admin_bypass_sets_flag():
    _, params = build_transactions_query("user-123", TransactionFilters(), include_all=True)
    assert params[0] == "user-123"
    assert params[1] == 1


def test_transactions_equality_filters_bind_in_order():
    filters = TransactionFilters(
        currency="NZD",
        direction="debit",
        spending_category="groceries",
        quality_status="ok",
    )
    sql, params = build_transactions_query("u1", filters)
    assert "currency = ?" in sql
    assert "direction = ?" in sql
    assert "spending_category = ?" in sql
    assert "quality_status = ?" in sql
    assert params[0] == "u1"
    assert params[1] == 0
    assert params[2:6] == ["NZD", "debit", "groceries", "ok"]
    assert params[-2:] == [0, 100]


def test_transactions_empty_string_filter_is_ignored():
    sql, params = build_transactions_query("u1", TransactionFilters(currency=""))
    assert "currency = ?" not in sql
    assert params == ["u1", 0, 0, 100]


def test_transactions_merchant_uses_like_on_two_columns():
    sql, params = build_transactions_query("u1", TransactionFilters(merchant="coffee"))
    assert "merchant_or_counterparty LIKE ?" in sql
    assert "expense_contributor LIKE ?" in sql
    assert params[2] == "%coffee%"
    assert params[3] == "%coffee%"


def test_transactions_review_required_maps_to_bit():
    sql_true, params_true = build_transactions_query("u1", TransactionFilters(review_required=True))
    assert "review_required = ?" in sql_true
    assert 1 in params_true
    _, params_false = build_transactions_query("u1", TransactionFilters(review_required=False))
    assert params_false.count(0) >= 2


def test_transactions_date_range_binds_bounds():
    sql, params = build_transactions_query(
        "u1", TransactionFilters(date_from="2026-01-01", date_to="2026-01-31")
    )
    assert "transaction_date >= ?" in sql
    assert "transaction_date <= ?" in sql
    assert "2026-01-01" in params
    assert "2026-01-31" in params


def test_transactions_limit_is_clamped_to_max():
    _, params = build_transactions_query("u1", TransactionFilters(limit=100000))
    assert params[-1] == 500


def test_transactions_bad_offset_defaults_to_zero():
    _, params = build_transactions_query("u1", TransactionFilters(offset=-5))
    assert params[-2] == 0


def test_document_provenance_query_scoped():
    sql, params = build_document_provenance_query("owner-9")
    assert "vw_reporting_document_provenance" in sql
    assert "(uploaded_by_user_id = ? OR ? = 1)" in sql
    assert params == ["owner-9", 0]


def test_document_provenance_admin_bypass():
    _, params = build_document_provenance_query("owner-9", include_all=True)
    assert params == ["owner-9", 1]


def test_document_detail_query_scoped_and_by_id():
    sql, params = build_document_detail_query("owner-9", "doc-1")
    assert "(uploaded_by_user_id = ? OR ? = 1) AND document_id = ?" in sql
    assert params == ["owner-9", 0, "doc-1"]


def test_document_detail_admin_bypass_keeps_id():
    _, params = build_document_detail_query("owner-9", "doc-1", include_all=True)
    assert params == ["owner-9", 1, "doc-1"]


def test_review_items_ordered_by_affected_amount():
    sql, params = build_review_items_query("u1", status="open", severity="high")
    assert "ORDER BY affected_expense_amount DESC" in sql
    assert params[0] == "u1"
    assert params[1] == 0
    assert "open" in params
    assert "high" in params


def test_review_items_admin_bypass():
    _, params = build_review_items_query("u1", include_all=True)
    assert params[0] == "u1"
    assert params[1] == 1


def test_findings_query_scoped_and_ordered():
    sql, params = build_findings_query("u1", status="open")
    assert "vw_reporting_findings" in sql
    assert "(uploaded_by_user_id = ? OR ? = 1)" in sql
    assert "ORDER BY affected_expense_amount DESC" in sql
    assert params[0] == "u1"
    assert params[1] == 0


def test_summarize_document_rows_rollups():
    rows = [
        {
            "document_type": "statement",
            "source_type": "upload",
            "source_institution": "Bank A",
            "status": "saved",
            "ocr_quality_status": "good",
            "transaction_count": 3,
            "review_item_count": 1,
            "created_at_utc": "2026-01-10",
        },
        {
            "document_type": "receipt",
            "source_type": "email",
            "source_institution": "Bank A",
            "status": "saved",
            "ocr_quality_status": None,
            "transaction_count": 2,
            "review_item_count": 0,
            "created_at_utc": "2026-02-01",
        },
    ]
    summary = summarize_document_rows(rows)
    assert summary["saved_documents"] == 2
    assert summary["by_document_type"] == {"statement": 1, "receipt": 1}
    assert summary["by_source_institution"] == {"Bank A": 2}
    assert summary["by_ocr_quality_status"]["unknown"] == 1
    assert summary["total_transaction_rows"] == 5
    assert summary["total_review_items"] == 1
    assert summary["latest_saved_document_utc"] == "2026-02-01"


def test_summarize_empty_rows():
    summary = summarize_document_rows([])
    assert summary["saved_documents"] == 0
    assert summary["total_transaction_rows"] == 0
    assert summary["latest_saved_document_utc"] is None


if __name__ == "__main__":
    import traceback

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception:  # noqa: BLE001
                failures += 1
                print(f"FAIL {name}")
                traceback.print_exc()
    print(f"\n{'ALL PASSED' if failures == 0 else str(failures) + ' FAILED'}")
    sys.exit(1 if failures else 0)
