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
from stats_data.duplicate_checks import DuplicateCheckResult
from stats_data.processing_jobs import ProcessingJob, ProcessingStep
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
        def rollback(self):
            captured["rolled_back"] = True

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

    def fake_append_processing_step(*_args, **_kwargs):
        raise RuntimeError("timing insert failed")

    monkeypatch.setattr("stats_data.api.append_processing_step", fake_append_processing_step)

    response = TestClient(app).post(
        "/api/v1/transactions/batches",
        json={
            "validation_result": result,
            "uploaded_by_user_id": "user_1",
            "saved_by_user_id": "user_1",
            "storage_reference": f"local-file://tests/input/{fixture_file.name}",
            "processing_job_id": "job_1",
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
    assert captured["rolled_back"] is True
    assert captured["closed"] is True


def test_duplicate_check_returns_review_status_before_save(monkeypatch):
    captured = {}
    result, fixture_file = _actual_validation_result()

    class FakeConnection:
        def close(self):
            captured["closed"] = True

    def fake_open_connection():
        captured["opened"] = True
        return FakeConnection()

    def fake_check(connection, result, **kwargs):
        captured["result"] = result
        captured["kwargs"] = kwargs
        return DuplicateCheckResult(
            duplicate_check_id="duplicate_check_1",
            validation_id=result["validation_id"],
            document_id="document_1",
            status="needs_review",
            summary={
                "total_checked": 2,
                "exact_file_duplicates": 0,
                "possible_document_duplicates": 1,
                "within_batch_duplicates": 0,
                "exact_transaction_duplicates": 0,
                "possible_transaction_duplicates": 1,
                "ready_to_save": 1,
            },
            document_results=[
                {
                    "result_scope": "document",
                    "match_type": "possible_same_document",
                    "match_status": "needs_review",
                    "matched_document_id": "document_existing",
                    "confidence": "0.88",
                    "reason_codes": ["MATCHED_DOCUMENT_FINGERPRINT"],
                    "message": "This document looks similar to one already saved.",
                }
            ],
            transaction_results=[
                {
                    "result_scope": "transaction",
                    "match_type": "possible_transaction_duplicate",
                    "match_status": "needs_review",
                    "record_id": "record_1",
                    "matched_transaction_id": "transaction_existing",
                    "confidence": "0.72",
                    "reason_codes": ["MATCHED_DATE_AMOUNT_CURRENCY_DIRECTION"],
                    "message": "This transaction has the same date, amount, currency, and direction as a saved transaction.",
                }
            ],
        )

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.check_validation_duplicates", fake_check)

    response = TestClient(app).post(
        "/api/v1/transactions/duplicate-checks",
        json={
            "validation_result": result,
            "uploaded_by_user_id": "user_1",
            "saved_by_user_id": "user_1",
            "storage_reference": f"local-file://tests/input/{fixture_file.name}",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "needs_review"
    assert payload["duplicate_check_id"] == "duplicate_check_1"
    assert payload["summary"]["possible_document_duplicates"] == 1
    assert payload["summary"]["possible_transaction_duplicates"] == 1
    assert payload["document_results"][0]["match_type"] == "possible_same_document"
    assert payload["transaction_results"][0]["record_id"] == "record_1"
    assert captured["kwargs"]["uploaded_by_user_id"] == "user_1"
    assert captured["kwargs"]["saved_by_user_id"] == "user_1"
    assert captured["closed"] is True


def test_processing_job_api_creates_updates_and_reads_job(monkeypatch):
    captured = {}

    class FakeConnection:
        def close(self):
            captured["closed"] = captured.get("closed", 0) + 1

    def fake_open_connection():
        captured["opened"] = captured.get("opened", 0) + 1
        return FakeConnection()

    def fake_create(connection, **kwargs):
        captured["create"] = kwargs
        return ProcessingJob(
            job_id="job_1",
            ingestion_id=kwargs["ingestion_id"],
            uploaded_by_user_id=kwargs["uploaded_by_user_id"],
            original_filename=kwargs["original_filename"],
            source_type=kwargs["source_type"],
            source_id=kwargs["source_id"],
            sha256=kwargs["sha256"],
            status="queued",
            stage="uploaded",
            message=kwargs["message"],
        )

    def fake_update(connection, job_id, **kwargs):
        captured["update"] = {"job_id": job_id, **kwargs}
        return ProcessingJob(
            job_id=job_id,
            ingestion_id="ingestion_1",
            uploaded_by_user_id="user_1",
            original_filename="receipt.jpg",
            source_type="manual_upload",
            source_id="stats-web-upload",
            sha256="abc123",
            status=kwargs["status"],
            stage=kwargs["stage"],
            message=kwargs["message"],
            parse_id=kwargs["parse_id"],
            extraction_id=kwargs["extraction_id"],
            validation_id=kwargs["validation_id"],
            result_payload=kwargs["result_payload"],
        )

    def fake_get(connection, job_id):
        captured["get"] = job_id
        return ProcessingJob(
            job_id=job_id,
            ingestion_id="ingestion_1",
            uploaded_by_user_id="user_1",
            original_filename="receipt.jpg",
            source_type="manual_upload",
            source_id="stats-web-upload",
            sha256="abc123",
            status="completed",
            stage="completed",
            message="Transactions checked.",
            result_payload={"validation_result": {"validation_id": "validation_1"}},
        )

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.create_processing_job", fake_create)
    monkeypatch.setattr("stats_data.api.update_processing_job", fake_update)
    monkeypatch.setattr("stats_data.api.get_processing_job", fake_get)
    client = TestClient(app)

    created = client.post(
        "/api/v1/processing-jobs",
        json={
            "ingestion_id": "ingestion_1",
            "uploaded_by_user_id": "user_1",
            "original_filename": "receipt.jpg",
            "source_type": "manual_upload",
            "source_id": "stats-web-upload",
            "sha256": "abc123",
            "message": "Queued",
        },
    )
    assert created.status_code == 200
    assert created.json()["job_id"] == "job_1"

    updated = client.patch(
        "/api/v1/processing-jobs/job_1",
        json={
            "status": "completed",
            "stage": "completed",
            "message": "Transactions checked.",
            "parse_id": "parse_1",
            "extraction_id": "extraction_1",
            "validation_id": "validation_1",
            "result_payload": {"validation_result": {"validation_id": "validation_1"}},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["result_payload"]["validation_result"]["validation_id"] == "validation_1"

    fetched = client.get("/api/v1/processing-jobs/job_1")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "completed"
    assert captured["create"]["original_filename"] == "receipt.jpg"
    assert captured["update"]["parse_id"] == "parse_1"
    assert captured["get"] == "job_1"


def test_processing_job_step_api_appends_and_lists_timing_rows(monkeypatch):
    captured = {}

    class FakeConnection:
        def close(self):
            captured["closed"] = captured.get("closed", 0) + 1

    def fake_open_connection():
        captured["opened"] = captured.get("opened", 0) + 1
        return FakeConnection()

    def fake_append(connection, job_id, **kwargs):
        captured["append"] = {"job_id": job_id, **kwargs}
        return ProcessingStep(
            step_id="step_1",
            job_id=job_id,
            document_id=kwargs["document_id"],
            correlation_id=kwargs["correlation_id"],
            module_name=kwargs["module_name"],
            step_name=kwargs["step_name"],
            status=kwargs["status"],
            started_at_utc=kwargs["started_at_utc"],
            completed_at_utc=kwargs["completed_at_utc"],
            duration_ms=kwargs["duration_ms"],
            metadata=kwargs["metadata"],
            error_code=kwargs["error_code"],
            error_message=kwargs["error_message"],
            created_at_utc="2026-06-07T01:02:03",
        )

    def fake_list(connection, job_id):
        captured["list"] = job_id
        return [
            ProcessingStep(
                step_id="step_1",
                job_id=job_id,
                document_id=None,
                correlation_id="corr_1",
                module_name="M5",
                step_name="document_parsing",
                status="completed",
                started_at_utc="2026-06-07T01:02:03Z",
                completed_at_utc="2026-06-07T01:02:15Z",
                duration_ms=12000,
                metadata={"parse_id": "parse_1", "pages_processed": 2},
                error_code=None,
                error_message=None,
                created_at_utc="2026-06-07T01:02:16",
            )
        ]

    monkeypatch.setattr("stats_data.api.open_azure_sql_connection", fake_open_connection)
    monkeypatch.setattr("stats_data.api.append_processing_step", fake_append)
    monkeypatch.setattr("stats_data.api.list_processing_steps", fake_list)
    client = TestClient(app)

    appended = client.post(
        "/api/v1/processing-jobs/job_1/steps",
        json={
            "module_name": "M5",
            "step_name": "document_parsing",
            "status": "completed",
            "started_at_utc": "2026-06-07T01:02:03Z",
            "completed_at_utc": "2026-06-07T01:02:15Z",
            "duration_ms": 12000,
            "correlation_id": "corr_1",
            "metadata": {"parse_id": "parse_1", "pages_processed": 2},
        },
    )
    assert appended.status_code == 200
    assert appended.json()["duration_ms"] == 12000
    assert appended.json()["metadata"]["parse_id"] == "parse_1"

    listed = client.get("/api/v1/processing-jobs/job_1/steps")
    assert listed.status_code == 200
    assert listed.json()["steps"][0]["step_name"] == "document_parsing"
    assert listed.json()["steps"][0]["metadata"]["pages_processed"] == 2
    assert captured["append"]["module_name"] == "M5"
    assert captured["list"] == "job_1"
    assert captured["closed"] == 2


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
