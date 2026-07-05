"""M9 - Stats Data and Persistence Start
Tests duplicate-check hardening behavior.
M9 End"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))

from stats_data.duplicate_checks import (  # noqa: E402
    check_validation_duplicates,
    _document_duplicate_results,
    _duplicate_check_result_operation,
    _row_dict,
    _transaction_duplicate_results,
)


def test_empty_duplicate_keys_do_not_create_exact_or_within_batch_matches():
    cursor = _DuplicateCursor()
    plan = SimpleNamespace(
        operations=[
            _operation({"transaction_id": "transaction_1", "source_candidate_id": "record_1", "duplicate_key": ""}),
            _operation({"transaction_id": "transaction_2", "source_candidate_id": "record_2", "duplicate_key": ""}),
        ]
    )

    rows = _transaction_duplicate_results(cursor, plan, owner_id="user_1")

    assert rows == []
    assert not any("where duplicate_key in" in query.lower() for query in cursor.queries)


def test_exact_duplicate_keys_are_loaded_in_one_batch_query():
    cursor = _DuplicateCursor(
        exact_rows=[
            _Row(duplicate_key="key_1", transaction_id="existing_transaction_1", document_id="document_existing")
        ]
    )
    plan = SimpleNamespace(
        operations=[
            _operation({"transaction_id": "transaction_1", "source_candidate_id": "record_1", "duplicate_key": "key_1"}),
            _operation({"transaction_id": "transaction_2", "source_candidate_id": "record_2", "duplicate_key": "key_2"}),
        ]
    )

    rows = _transaction_duplicate_results(cursor, plan, owner_id="user_1")

    exact_queries = [query for query in cursor.queries if "where duplicate_key in" in query.lower()]
    assert len(exact_queries) == 1
    assert rows[0]["match_type"] == "exact_transaction_duplicate"
    assert rows[0]["matched_transaction_id"] == "existing_transaction_1"


def test_empty_document_fingerprint_evidence_is_not_matched():
    cursor = _DuplicateCursor(document_rows=[_Row(document_id="existing_document", original_filename="old.pdf")])
    result = {"document": {}, "normalized_records": [], "validated_entities": [], "validated_references": []}
    plan = SimpleNamespace(document_id="current_document")

    rows = _document_duplicate_results(cursor, result, plan, uploaded_by_user_id="user_1")

    assert rows == []
    assert not any("document_fingerprint" in query.lower() for query in cursor.queries)


def test_duplicate_check_result_id_uses_row_content_not_position():
    row = {
        "result_scope": "transaction",
        "match_type": "possible_transaction_duplicate",
        "match_status": "needs_review",
        "record_id": "record_1",
        "matched_document_id": "document_1",
        "matched_transaction_id": "transaction_1",
        "confidence": "0.72",
        "reason_codes": ["MATCHED_DATE_AMOUNT_CURRENCY_DIRECTION"],
        "message": "Possible duplicate.",
    }

    first = _duplicate_check_result_operation(
        duplicate_check_id="duplicate_check_1",
        candidate_document_id="document_current",
        index=1,
        row=row,
    )
    second = _duplicate_check_result_operation(
        duplicate_check_id="duplicate_check_1",
        candidate_document_id="document_current",
        index=2,
        row=row,
    )

    assert first.values["duplicate_check_result_id"] == second.values["duplicate_check_result_id"]
    assert first.values["document_id"] is None
    assert first.values["candidate_document_id"] == "document_current"


def test_duplicate_check_does_not_persist_candidate_document_shell():
    connection = _DuplicateCheckConnection(
        document_rows=[_Row(document_id="existing_document", original_filename="statement.pdf")]
    )
    result = {
        "validation_id": "validation_duplicate_file",
        "status": "valid",
        "document_type": "statement",
        "document": {
            "ingestion_id": "ingestion_duplicate_file",
            "original_filename": "statement.pdf",
            "normalized_filename": "statement.pdf",
            "sha256": "same-file-hash",
        },
        "summary": {
            "normalized_record_count": 0,
            "valid_record_count": 0,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "normalized_records": [],
        "validated_entities": [],
        "validated_references": [],
    }

    duplicate_check = check_validation_duplicates(connection, result, uploaded_by_user_id="user_1")

    executed = "\n".join(connection.cursor_instance.queries).lower()
    assert duplicate_check.status == "blocked"
    assert duplicate_check.summary["exact_file_duplicates"] == 1
    assert "merge dbo.[stats_documents]" not in executed
    assert "merge dbo.[validation_results]" not in executed
    assert "merge dbo.[duplicate_check_batches]" in executed
    assert "merge dbo.[duplicate_check_results]" in executed
    assert "candidate_document_id" in executed
    assert connection.committed is True


def test_row_dict_prefers_named_access_over_position_fallback():
    row = _NamedMappingRow({"transaction_id": "transaction_named", "document_id": "document_named"})

    assert _row_dict(row, ["transaction_id", "document_id"]) == {
        "transaction_id": "transaction_named",
        "document_id": "document_named",
    }


def _operation(values: dict):
    return SimpleNamespace(table="transactions", values=values)


class _DuplicateCursor:
    def __init__(self, *, exact_rows=None, possible_rows=None, document_rows=None):
        self.exact_rows = exact_rows or []
        self.possible_rows = possible_rows or []
        self.document_rows = document_rows or []
        self.queries: list[str] = []
        self._next_rows = []

    def execute(self, sql, *params):
        self.queries.append(sql)
        lowered = sql.lower()
        if "duplicate_key in" in lowered:
            self._next_rows = self.exact_rows
        elif "from dbo.stats_documents" in lowered:
            self._next_rows = self.document_rows
        else:
            self._next_rows = self.possible_rows

    def fetchall(self):
        rows = self._next_rows
        self._next_rows = []
        return rows


class _DuplicateCheckConnection:
    def __init__(self, *, document_rows=None):
        self.cursor_instance = _DuplicateCursor(document_rows=document_rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _Row:
    def __init__(self, **values):
        self._values = values
        for key, value in values.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self._values.values())[key]
        return self._values[key]


class _NamedMappingRow:
    def __init__(self, values: dict):
        self.values = values

    def __getitem__(self, key):
        if isinstance(key, int):
            return f"wrong_position_{key}"
        return self.values[key]
