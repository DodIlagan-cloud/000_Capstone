"""M9 - Stats Data and Persistence Start
Tests validation result persistence using configured real test input.
M9 End"""

from __future__ import annotations

import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
STATS_DATA_SCRIPTS = REPO_ROOT / "apps" / "stats-data" / "scripts"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))
if str(STATS_DATA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SCRIPTS))

from stats_data.validation_persistence import (  # noqa: E402
    build_validation_persistence_plan,
    build_validation_persistence_plan_from_temp_file,
    delete_uploaded_document_records,
    list_recent_uploaded_documents,
    load_validation_payload_temp_file,
    persist_validation_result_with_temp_handoff,
    table_counts,
    write_validation_payload_temp_file,
)


def test_build_validation_persistence_plan_uses_real_document_pipeline_output():
    result, fixture_file = _actual_validation_result()

    plan = build_validation_persistence_plan(
        result,
        uploaded_by_user_id=os.environ.get("STATS_TEST_USER_ID", "local-real-fixture-user"),
        storage_reference=f"local-file://tests/input/{fixture_file.name}",
    )
    counts = table_counts(plan.operations)

    assert result["document"]["original_filename"] == fixture_file.name
    assert result["parse_id"].startswith("parse_")
    assert result["extraction_id"].startswith("extract_")
    assert result["validation_id"].startswith("validate_")
    assert counts["validation_results"] == 1
    assert counts["stats_documents"] == 1
    assert counts["processing_runs"] == 1
    assert counts["transaction_batches"] == 1
    assert counts.get("transactions", 0) == result["summary"]["normalized_record_count"]
    assert counts.get("financial_fields", 0) == result["summary"]["financial_field_count"]
    assert counts.get("document_sections", 0) == result["summary"]["section_candidate_count"]
    assert counts.get("validated_entities", 0) == result["summary"]["entity_count"]
    assert counts.get("validated_references", 0) == result["summary"]["reference_count"]
    assert counts.get("line_items", 0) == result["summary"]["line_item_count"]
    assert counts.get("installments", 0) == result["summary"]["installment_count"]
    if result["document_financial_summary"]:
        assert counts.get("statement_summaries", 0) == 1
        assert counts.get("document_financial_summaries", 0) == 1

    staging = _only(plan, "validation_results")
    assert staging["payload_json"].startswith("{")
    assert staging["section_candidate_count"] == result["summary"]["section_candidate_count"]
    assert staging["entity_count"] == result["summary"]["entity_count"]
    assert staging["reference_count"] == result["summary"]["reference_count"]
    assert fixture_file.name in staging["payload_json"]

    document = _only(plan, "stats_documents")
    assert document["original_filename"] == fixture_file.name
    assert document["storage_reference"] == f"local-file://tests/input/{fixture_file.name}"

    if result["normalized_records"]:
        transaction = _only(plan, "transactions")
        assert transaction["normalized_description"]
        assert transaction["duplicate_key"]

    if result["document_financial_summary"]:
        statement_summary = _only(plan, "statement_summaries")
        document_financial_summary = _only(plan, "document_financial_summaries")
        assert statement_summary["document_id"] == plan.document_id
        assert document_financial_summary["document_id"] == plan.document_id
        assert statement_summary["quality_status"] in {"valid", "warning", "invalid"}
        assert document_financial_summary["quality_status"] in {"valid", "warning", "invalid"}


def test_build_validation_persistence_plan_is_deterministic_for_real_validation_output():
    result, _fixture_file = _actual_validation_result()

    first = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    second = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")

    first_ids = [(operation.table, operation.values[operation.key_column]) for operation in first.operations]
    second_ids = [(operation.table, operation.values[operation.key_column]) for operation in second.operations]

    assert first.document_id == second.document_id
    assert first_ids == second_ids


def test_validation_temp_handoff_file_uses_central_configured_directory(monkeypatch, tmp_path):
    result, fixture_file = _actual_validation_result()
    handoff_dir = tmp_path / "configured-validation-handoff"
    monkeypatch.setenv("STATS_VALIDATION_HANDOFF_DIR", str(handoff_dir))

    handoff_file = write_validation_payload_temp_file(result)
    loaded_result = load_validation_payload_temp_file(handoff_file)
    plan = build_validation_persistence_plan_from_temp_file(
        handoff_file,
        uploaded_by_user_id="local-real-fixture-user",
        storage_reference=f"local-file://tests/input/{fixture_file.name}",
    )

    assert handoff_file.exists()
    assert handoff_file.parent == handoff_dir
    assert handoff_file.name.endswith(".validation.json")
    assert loaded_result["validation_id"] == result["validation_id"]
    assert loaded_result["document"]["original_filename"] == fixture_file.name
    assert plan.validation_id == result["validation_id"]
    assert _only(plan, "stats_documents")["original_filename"] == fixture_file.name


def test_persist_validation_result_writes_real_fixture_to_configured_azure_sql():
    connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING", "").strip()
    if not connection_string:
        pytest.skip("Set AZURE_SQL_CONNECTIONSTRING to run the live M9 Azure SQL persistence test.")

    pyodbc = pytest.importorskip("pyodbc")
    from apply_azure_sql_migrations import _apply_migration, _normalize_connection_string

    result, fixture_file = _actual_validation_result()
    connection = pyodbc.connect(_normalize_connection_string(connection_string), timeout=30, autocommit=False)

    try:
        cursor = connection.cursor()
        for migration_file in sorted((REPO_ROOT / "apps" / "stats-data" / "migrations" / "azure-sql").glob("*.sql")):
            _apply_migration(cursor, migration_file)
            connection.commit()

        temp_dir = REPO_ROOT / "test-results" / "m9-live-handoff"
        plan = persist_validation_result_with_temp_handoff(
            connection,
            result,
            temp_dir=temp_dir,
            uploaded_by_user_id=os.environ.get("STATS_TEST_USER_ID", "local-real-fixture-user"),
            storage_reference=f"local-file://tests/input/{fixture_file.name}",
        )

        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT vr.validation_id, sd.original_filename, vr.promotion_status
            FROM dbo.validation_results AS vr
            INNER JOIN dbo.stats_documents AS sd
                ON sd.validation_result_id = vr.validation_result_id
            WHERE vr.validation_result_id = ?
            """,
            plan.validation_result_id,
        )
        row = cursor.fetchone()

        assert row is not None
        assert row.validation_id == result["validation_id"]
        assert row.original_filename == fixture_file.name
        assert row.promotion_status == "promoted"
        assert not list(temp_dir.glob(f"{result['validation_id']}*.validation.json"))
    finally:
        connection.close()


def test_delete_uploaded_document_records_removes_child_rows_before_document():
    connection = _FakeDeleteConnection()

    result = delete_uploaded_document_records(connection, "document_1")

    delete_tables = [
        entry["table"]
        for entry in connection.cursor_instance.executions
        if entry["kind"] == "delete"
    ]

    assert result.document_id == "document_1"
    assert result.validation_result_id == "validation_result_1"
    assert result.deleted_counts["stats_documents"] == 1
    assert result.deleted_counts["validation_results"] == 1
    assert delete_tables.index("review_items") < delete_tables.index("transactions")
    assert delete_tables.index("findings") < delete_tables.index("transactions")
    assert delete_tables.index("transactions") < delete_tables.index("transaction_batches")
    assert delete_tables.index("transaction_batches") < delete_tables.index("stats_documents")
    assert delete_tables.index("stats_documents") < delete_tables.index("validation_results")
    assert connection.committed is True
    assert connection.rolled_back is False


def test_list_recent_uploaded_documents_returns_frontend_summary_rows():
    connection = _FakeListConnection()

    documents = list_recent_uploaded_documents(connection, limit=5)

    assert len(documents) == 1
    assert documents[0].document_id == "document_1"
    assert documents[0].original_filename == "201911_BPICHK.pdf"
    assert documents[0].transaction_count == 16
    assert documents[0].financial_field_count == 9
    assert documents[0].review_item_count == 15
    assert "top (5)" in connection.cursor_instance.executed_sql.lower()
    assert connection.cursor_instance.executed_sql.lower().find("stats_documents") < connection.cursor_instance.executed_sql.lower().find("order by")


def _actual_validation_result() -> tuple[dict[str, Any], Path]:
    for fixture_file in _real_input_files():
        try:
            result = _run_document_validation_pipeline(fixture_file)
        except Exception:
            continue
        if result["summary"]["normalized_record_count"] or result["summary"]["financial_field_count"]:
            return result, fixture_file

    pytest.skip("No configured tests/input fixture produced validation output for M9 persistence.")


def _run_document_validation_pipeline(fixture_file: Path) -> dict[str, Any]:
    parsing_root = REPO_ROOT / "modules" / "document-parsing-module"
    _activate_app_module(parsing_root)
    from app.services.parsing_service import parse_document_content

    content = fixture_file.read_bytes()
    content_type = mimetypes.guess_type(fixture_file.name)[0]
    parsed = parse_document_content(
        content=content,
        filename=fixture_file.name,
        provided_content_type=content_type,
        ingestion_id=f"ingest_{fixture_file.stem.lower()}",
        source_type="configured_test_input",
        source_id=str(fixture_file.relative_to(REPO_ROOT)).replace("\\", "/"),
        allow_ocr_fallback=fixture_file.suffix.lower() not in {".pdf"},
        page_limit=int(os.environ.get("STATS_TEST_PAGE_LIMIT", "2")),
    )

    extraction_root = REPO_ROOT / "modules" / "transaction-extraction-module"
    _activate_app_module(extraction_root)
    from app.models.extraction import TransactionExtractionRequest
    from app.services.extraction_service import extract_transactions

    extraction_request = TransactionExtractionRequest(
        parse_id=parsed.parse_id,
        document=_dump_model(parsed.document),
        document_type=parsed.classification.document_type,
        classification_confidence=parsed.classification.confidence,
        classification=_dump_model(parsed.classification),
        text=parsed.text,
        pages=[_dump_model(page) for page in parsed.pages],
        metadata=_dump_model(parsed.metadata),
        quality=_dump_model(parsed.quality),
        findings=[_dump_model(finding) for finding in parsed.findings],
    )
    extracted = extract_transactions(extraction_request)

    validation_root = REPO_ROOT / "modules" / "data-validation-module"
    _activate_app_module(validation_root)
    from app.models.validation import DataValidationRequest
    from app.services.validation_service import validate_data

    validation_request = DataValidationRequest(
        extraction_id=extracted.extraction_id,
        parse_id=extracted.parse_id,
        document=_dump_model(extracted.document),
        document_type=extracted.document_type,
        transaction_candidates=[_dump_model(candidate) for candidate in extracted.transaction_candidates],
        financial_field_candidates=[_dump_model(candidate) for candidate in extracted.financial_field_candidates],
        section_candidates=[_dump_model(candidate) for candidate in extracted.section_candidates],
        entity_candidates=[_dump_model(candidate) for candidate in extracted.entity_candidates],
        reference_candidates=[_dump_model(candidate) for candidate in extracted.reference_candidates],
        line_item_candidates=[_dump_model(candidate) for candidate in extracted.line_item_candidates],
        installment_candidates=[_dump_model(candidate) for candidate in extracted.installment_candidates],
        reconciliation=_dump_model(extracted.reconciliation),
        findings=[_dump_model(finding) for finding in extracted.findings],
    )
    return _dump_model(validate_data(validation_request))


def _real_input_files() -> list[Path]:
    configured = os.environ.get("STATS_TESTDATA_DIR")
    input_dir = Path(configured) if configured else REPO_ROOT / "tests" / "input"
    if not input_dir.exists():
        pytest.skip(f"Configured real test-data directory does not exist: {input_dir}")

    explicit_fixture = os.environ.get("STATS_M9_TEST_FIXTURE")
    if explicit_fixture:
        fixture_file = Path(explicit_fixture)
        if not fixture_file.is_absolute():
            fixture_file = input_dir / fixture_file
        if not fixture_file.exists():
            pytest.skip(f"Configured STATS_M9_TEST_FIXTURE does not exist: {fixture_file}")
        return [fixture_file]

    suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    files = [path for path in sorted(input_dir.iterdir()) if path.is_file() and path.suffix.lower() in suffixes]
    if not files:
        pytest.skip(f"No real document fixtures found in configured test-data directory: {input_dir}")

    return sorted(files, key=lambda path: (path.suffix.lower() != ".pdf", path.name.lower()))


def _activate_app_module(module_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]
    module_root_path = str(module_root)
    if module_root_path in sys.path:
        sys.path.remove(module_root_path)
    sys.path.insert(0, module_root_path)


def _dump_model(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _only(plan, table):
    return [operation.values for operation in plan.operations if operation.table == table][0]


class _FakeRow:
    def __init__(self, *values):
        self._values = values

    def __getitem__(self, index):
        return self._values[index]


class _FakeDeleteCursor:
    def __init__(self):
        self.executions = []
        self.rowcount = -1
        self._next_row = None

    def execute(self, sql, *params):
        normalized = " ".join(sql.split()).lower()
        table = _delete_table_name(normalized)
        if normalized.startswith("select validation_result_id"):
            self._next_row = _FakeRow("validation_result_1")
            self.rowcount = -1
            self.executions.append({"kind": "select", "table": "stats_documents", "params": params})
        elif normalized.startswith("select count(1)"):
            self._next_row = _FakeRow(0)
            self.rowcount = -1
            self.executions.append({"kind": "select", "table": "stats_documents", "params": params})
        elif normalized.startswith("delete"):
            self._next_row = None
            self.rowcount = 1
            self.executions.append({"kind": "delete", "table": table, "params": params})
        else:
            self._next_row = None
            self.rowcount = 1
            self.executions.append({"kind": "statement", "table": table, "params": params})
        return self

    def fetchone(self):
        return self._next_row


class _FakeDeleteConnection:
    def __init__(self):
        self.cursor_instance = _FakeDeleteCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _FakeListRow:
    document_id = "document_1"
    original_filename = "201911_BPICHK.pdf"
    document_type = "statement"
    status = "needs_review"
    source_institution = "BPI"
    created_at_utc = "2026-06-05T11:41:23"
    updated_at_utc = "2026-06-05T11:41:23"
    uploaded_by_user_id = "user_1"
    storage_reference = "local-file://tests/input/201911_BPICHK.pdf"
    validation_result_id = "validation_result_1"
    transaction_count = 16
    financial_field_count = 9
    review_item_count = 15


class _FakeListCursor:
    def __init__(self):
        self.executed_sql = ""

    def execute(self, sql, *params):
        self.executed_sql = sql
        return self

    def fetchall(self):
        return [_FakeListRow()]


class _FakeListConnection:
    def __init__(self):
        self.cursor_instance = _FakeListCursor()

    def cursor(self):
        return self.cursor_instance


def _delete_table_name(normalized_sql: str) -> str | None:
    match = re.search(r"(?:delete from|update) dbo\.([a-z_]+)", normalized_sql)
    return match.group(1) if match else None
