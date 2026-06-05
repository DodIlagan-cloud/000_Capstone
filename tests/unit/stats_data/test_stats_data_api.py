"""M9 - Stats Data and Persistence Start
Tests the Stats Data persistence API boundary.
M9 End"""

from pathlib import Path
import importlib.util
import sys

from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))

from stats_data.api import app
from stats_data.validation_persistence import (
    DeleteDocumentResult,
    UploadedDocumentSummary,
    build_validation_persistence_plan,
)


_fixture_module_path = Path(__file__).with_name("test_validation_persistence.py")
_fixture_spec = importlib.util.spec_from_file_location("stats_data_validation_fixture_helpers", _fixture_module_path)
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
assert _fixture_spec and _fixture_spec.loader
_fixture_spec.loader.exec_module(_fixture_module)
_actual_validation_result = _fixture_module._actual_validation_result


def test_save_transactions_batch_returns_persisted_summary(monkeypatch):
    captured = {}
    result, fixture_file = _actual_validation_result()

    class FakeConnection:
        def close(self):
            captured["closed"] = True

    def fake_open_connection():
        captured["opened"] = True
        return FakeConnection()

    def fake_persist(connection, result, **kwargs):
        captured["result"] = result
        captured["kwargs"] = kwargs
        return build_validation_persistence_plan(
            result,
            uploaded_by_user_id=kwargs.get("uploaded_by_user_id"),
            saved_by_user_id=kwargs.get("saved_by_user_id"),
            storage_reference=kwargs.get("storage_reference"),
        )

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.persist_validation_result_with_temp_handoff", fake_persist)

    response = TestClient(app).post(
        "/api/v1/transactions/batches",
        json={
            "validation_result": result,
            "uploaded_by_user_id": "user_1",
            "saved_by_user_id": "user_1",
            "storage_reference": f"local-file://tests/input/{fixture_file.name}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "saved"
    assert payload["validation_id"] == result["validation_id"]
    assert payload["transaction_batch_id"]
    assert payload["saved_record_count"] == result["summary"]["valid_record_count"]
    assert payload["persisted_counts"].get("transactions", 0) == result["summary"]["normalized_record_count"]
    assert captured["kwargs"]["uploaded_by_user_id"] == "user_1"
    assert captured["kwargs"]["saved_by_user_id"] == "user_1"
    assert captured["result"]["document"]["original_filename"] == fixture_file.name
    assert captured["closed"] is True


def test_delete_uploaded_document_removes_saved_document_records(monkeypatch):
    captured = {}
    document_id = "document_1"

    class FakeConnection:
        def close(self):
            captured["closed"] = True

    def fake_open_connection():
        captured["opened"] = True
        return FakeConnection()

    def fake_delete(connection, requested_document_id):
        captured["document_id"] = requested_document_id
        return DeleteDocumentResult(
            document_id=requested_document_id,
            validation_result_id="validation_result_1",
            deleted_counts={
                "review_items": 2,
                "transactions": 3,
                "transaction_batches": 1,
                "stats_documents": 1,
                "validation_results": 1,
            },
        )

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.delete_uploaded_document_records", fake_delete)

    response = TestClient(app).delete(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "deleted"
    assert payload["document_id"] == document_id
    assert payload["validation_result_id"] == "validation_result_1"
    assert payload["deleted_counts"]["stats_documents"] == 1
    assert captured["document_id"] == document_id
    assert captured["closed"] is True


def test_recent_uploaded_documents_returns_documents_for_frontend(monkeypatch):
    captured = {}

    class FakeConnection:
        def close(self):
            captured["closed"] = True

    def fake_open_connection():
        captured["opened"] = True
        return FakeConnection()

    def fake_list(connection, *, limit):
        captured["limit"] = limit
        return [
            UploadedDocumentSummary(
                document_id="document_1",
                original_filename="201911_BPICHK.pdf",
                document_type="statement",
                status="needs_review",
                source_institution="BPI",
                created_at_utc="2026-06-05T11:41:23",
                updated_at_utc="2026-06-05T11:41:23",
                uploaded_by_user_id="user_1",
                storage_reference="local-file://tests/input/201911_BPICHK.pdf",
                validation_result_id="validation_result_1",
                transaction_count=16,
                financial_field_count=9,
                review_item_count=15,
            )
        ]

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.list_recent_uploaded_documents", fake_list)

    response = TestClient(app).get("/api/v1/documents?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"][0]["document_id"] == "document_1"
    assert payload["documents"][0]["transaction_count"] == 16
    assert captured["limit"] == 10
    assert captured["closed"] is True


def test_delete_uploaded_document_returns_not_found_when_document_is_absent(monkeypatch):
    class FakeConnection:
        def close(self):
            pass

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", lambda: FakeConnection())
    monkeypatch.setattr(
        "stats_data.api.delete_uploaded_document_records",
        lambda connection, document_id: DeleteDocumentResult(
            document_id=document_id,
            validation_result_id=None,
            deleted_counts={},
        ),
    )

    response = TestClient(app).delete("/api/v1/documents/missing-document")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document was not found."
