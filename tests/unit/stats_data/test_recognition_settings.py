"""M9 - Stats Data and Persistence Start
Tests recognition settings governance hardening.
M9 End"""

from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))

from stats_data import recognition_settings


class RecordingCursor:
    def __init__(self, *, rowcount: int = 1, fetchone_results: list[object | None] | None = None):
        self.rowcount = rowcount
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetchone_results = list(fetchone_results or [])

    def execute(self, sql: str, *params: object) -> None:
        self.calls.append((sql, params))

    def fetchone(self) -> object | None:
        if self.fetchone_results:
            return self.fetchone_results.pop(0)
        return None


class RecordingConnection:
    def __init__(self, cursor: RecordingCursor):
        self._cursor = cursor
        self.committed = False

    def cursor(self) -> RecordingCursor:
        return self._cursor

    def commit(self) -> None:
        self.committed = True


def test_record_sync_run_uses_config_change_id_from_config_change():
    cursor = RecordingCursor()

    config_change_id = recognition_settings._record_config_change(
        cursor,
        "suggestion_123",
        "admin_1",
        "approve_suggestion",
        "approved for test",
    )
    recognition_settings._record_sync_run(cursor, config_change_id, 3)

    assert config_change_id.startswith("config_change_")
    sync_sql, sync_params = cursor.calls[-1]
    assert "recognition_label_sync_runs" in sync_sql
    assert sync_params[1] == config_change_id
    assert sync_params[1] != "suggestion_123"


def test_review_suggestion_already_reviewed_does_not_write_audit(monkeypatch):
    cursor = RecordingCursor()
    connection = RecordingConnection(cursor)
    monkeypatch.setattr(
        recognition_settings,
        "_suggestion",
        lambda _cursor, _suggestion_id: {
            "suggestion_id": "suggestion_approved",
            "suggestion_status": "approved",
            "suggested_transaction_type": "purchase",
        },
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("terminal suggestion should not create new audit rows")

    monkeypatch.setattr(recognition_settings, "_record_config_change", fail_if_called)
    monkeypatch.setattr(recognition_settings, "_record_sync_run", fail_if_called)

    result = recognition_settings.review_suggestion(
        connection,
        suggestion_id="suggestion_approved",
        action="approve",
        admin_user_id="admin_1",
    )

    assert result["already_reviewed"] is True
    assert result["status"] == "approved"
    assert connection.committed is False


def test_save_label_rename_reports_missing_source_label():
    cursor = RecordingCursor(rowcount=0)
    connection = RecordingConnection(cursor)

    with pytest.raises(ValueError, match="not found"):
        recognition_settings.save_label(
            connection,
            scope="document",
            original_label="missing_receipt",
            label="receipt",
            values=["sales_receipt"],
        )

    assert connection.committed is False


def test_seed_recognition_settings_uses_idempotent_insert_merge_not_count_gate():
    cursor = RecordingCursor()
    connection = RecordingConnection(cursor)

    recognition_settings.seed_recognition_settings_if_empty(connection)

    sql_text = "\n".join(sql for sql, _params in cursor.calls)
    assert "SELECT COUNT(1)" not in sql_text
    assert "SELECT TOP (1) 1 FROM dbo.recognition_labels" in sql_text
    assert "SELECT TOP (1) 1 FROM dbo.recognition_rules" in sql_text
    assert "MERGE dbo.recognition_labels WITH (HOLDLOCK)" in sql_text
    assert "MERGE dbo.recognition_rules WITH (HOLDLOCK)" in sql_text
    assert "WHEN MATCHED THEN" not in sql_text
    assert connection.committed is True


def test_seed_recognition_settings_skips_when_database_is_already_seeded():
    cursor = RecordingCursor(fetchone_results=[(1,), (1,)])
    connection = RecordingConnection(cursor)

    recognition_settings.seed_recognition_settings_if_empty(connection)

    sql_text = "\n".join(sql for sql, _params in cursor.calls)
    assert "MERGE dbo.recognition_labels" not in sql_text
    assert "MERGE dbo.recognition_rules" not in sql_text
    assert connection.committed is False


def test_active_recognition_settings_includes_versioned_ai_context(monkeypatch):
    cursor = RecordingCursor()
    connection = RecordingConnection(cursor)
    monkeypatch.setattr(recognition_settings, "seed_recognition_settings_if_empty", lambda _connection: None)
    monkeypatch.setattr(
        recognition_settings,
        "_load_labels",
        lambda _connection: {
            "document": {"receipt": ["payment_terminal_receipt"], "unknown": ["unknown"]},
            "transaction": {"purchase": ["card_purchase"], "unknown": ["unknown"]},
            "spending": {"transport": ["stored_value_topup"], "uncategorized": ["unknown"]},
        },
    )
    monkeypatch.setattr(
        recognition_settings,
        "_load_rules",
        lambda _connection: {
            "document": [{"document_type": "receipt", "document_subtype": "payment_terminal_receipt"}],
            "transaction": [{"transaction_type": "purchase", "transaction_subtype": "card_purchase"}],
            "spending": [{"spending_category": "transport", "spending_subcategory": "stored_value_topup"}],
        },
    )

    payload = recognition_settings.active_recognition_settings(connection)

    assert payload["recognition_context_version"] == payload["recognition_context"]["version"]
    assert len(payload["recognition_context_version"]) == 16
    assert payload["recognition_context"]["transaction"]["vocabulary"]["transaction_types"] == ["purchase", "unknown"]
    assert payload["recognition_context"]["spending"]["vocabulary"]["spending_categories"] == ["transport", "uncategorized"]
