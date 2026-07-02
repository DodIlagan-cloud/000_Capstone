"""M12 - Email Ingestion Module Start
Unit tests for the folded automated pipeline orchestrator (app/pipeline).

These use a fake clients object, so they exercise the orchestration sequence,
governed-save behaviour, idempotency contract, and failure handling without httpx,
pydantic, or a live network.
M12 End"""

import base64

from app.pipeline.models import PipelineRunRequest
from app.pipeline.orchestrator import run_automated_pipeline
from app.pipeline.request_builders import build_extraction_request, build_validation_request


PDF_BYTES = b"%PDF-1.4\nautomated fixture\n%%EOF"


def _request(**overrides) -> PipelineRunRequest:
    base = dict(
        ingestion_id="ingest_email_001",
        original_filename="statement.pdf",
        source_type="email_attachment",
        source_id="mailbox-primary:msg-1:att-1",
        sha256="abc123",
        content_base64=base64.b64encode(PDF_BYTES).decode("ascii"),
        content_type="application/pdf",
        correlation_id="email_corr_001",
    )
    base.update(overrides)
    return PipelineRunRequest(**base)


class FakeClients:
    def __init__(self, parse=None, save=None, fail_step=None, fetch_none=False):
        self.calls = []
        self.job_updates = []
        self._fetch_none = fetch_none
        self._parse = parse or {"parse_id": "parse_1", "status": "completed", "document": {"ingestion_id": "ingest_email_001"}}
        self._save = save or {
            "document_id": "doc_1",
            "saved_record_count": 3,
            "review_item_count": 1,
            "warning_record_count": 1,
            "invalid_record_count": 0,
        }
        self._fail_step = fail_step
        self.save_args = None

    def _maybe_fail(self, step):
        if self._fail_step == step:
            raise RuntimeError(f"{step} boom")

    def fetch_content(self, request):
        self.calls.append("fetch_content")
        return b"" if self._fetch_none else PDF_BYTES

    def create_job(self, request):
        self.calls.append("create_job")
        return "job_1"

    def update_job(self, job_id, **fields):
        self.job_updates.append({"job_id": job_id, **fields})

    def parse(self, content, request):
        self.calls.append("parse")
        self._maybe_fail("parse")
        assert content == PDF_BYTES
        return self._parse

    def extract(self, parse_result):
        self.calls.append("extract")
        self._maybe_fail("extract")
        return {"extraction_id": "extract_1", "transaction_candidates": [{"amount": 1}]}

    def fetch_recognition_context(self):
        self.calls.append("recognition_context")
        return {"document_types": ["bank_statement"]}

    def validate(self, extraction_result, recognition_context):
        self.calls.append("validate")
        self._maybe_fail("validate")
        return {"validation_id": "validate_1", "summary": {"valid_record_count": 3}}

    def save(self, validation_result, request, job_id):
        self.calls.append("save")
        self._maybe_fail("save")
        self.save_args = {"validation_result": validation_result, "request": request, "job_id": job_id}
        return self._save


def test_happy_path_runs_full_sequence_and_saves():
    clients = FakeClients()
    result = run_automated_pipeline(_request(), clients)

    assert result.status == "completed"
    assert clients.calls == ["create_job", "parse", "extract", "recognition_context", "validate", "save"]
    assert result.document_id == "doc_1"
    assert result.saved_record_count == 3
    assert result.review_item_count == 1
    assert result.parse_id == "parse_1"
    assert result.extraction_id == "extract_1"
    assert result.validation_id == "validate_1"
    assert any(update.get("stage") == "saving" for update in clients.job_updates)
    assert any(update.get("stage") == "completed" for update in clients.job_updates)


def test_governed_save_uses_system_identity_not_a_real_user():
    clients = FakeClients()
    run_automated_pipeline(_request(uploaded_by_user_id=None), clients)
    assert clients.save_args["job_id"] == "job_1"
    assert clients.save_args["request"].source_type == "email_attachment"


def test_missing_inline_content_is_fetched_from_intake():
    clients = FakeClients()
    result = run_automated_pipeline(_request(content_base64=None), clients)

    assert result.status == "completed"
    # Content is fetched from intake first, then the normal sequence runs.
    assert clients.calls[0] == "fetch_content"
    assert clients.calls[1:] == ["create_job", "parse", "extract", "recognition_context", "validate", "save"]


def test_unavailable_stored_content_fails_before_creating_a_job():
    clients = FakeClients(fetch_none=True)
    result = run_automated_pipeline(_request(content_base64=None), clients)

    assert result.status == "failed"
    assert result.job_id is None
    assert clients.calls == ["fetch_content"]
    assert "intake content" in result.error.lower()


def test_parse_failure_stops_before_save_and_marks_job_failed():
    clients = FakeClients(parse={"parse_id": "parse_x", "status": "failed"})
    result = run_automated_pipeline(_request(), clients)

    assert result.status == "failed"
    assert "save" not in clients.calls
    assert clients.calls == ["create_job", "parse"]
    assert any(update.get("status") == "failed" for update in clients.job_updates)


def test_downstream_exception_marks_job_failed_and_does_not_raise():
    clients = FakeClients(fail_step="validate")
    result = run_automated_pipeline(_request(), clients)

    assert result.status == "failed"
    assert "save" not in clients.calls
    assert result.error
    assert any(update.get("status") == "failed" for update in clients.job_updates)


def test_build_extraction_request_passes_through_parse_fields():
    parse_result = {
        "parse_id": "p1",
        "document": {"ingestion_id": "i1", "original_filename": "f.pdf"},
        "classification": {"document_type": "bank_statement", "confidence": 0.9},
        "text": "hello",
    }
    built = build_extraction_request(parse_result)
    assert built["parse_id"] == "p1"
    assert built["document"]["ingestion_id"] == "i1"
    assert built["document_type"] == "bank_statement"
    assert built["text"] == "hello"
    assert built["pages"] == []


def test_build_validation_request_carries_candidates_and_context():
    extraction_result = {
        "extraction_id": "e1",
        "parse_id": "p1",
        "transaction_candidates": [{"amount": 10}],
        "classification": {"confidence": 0.8, "status": "recognized"},
    }
    built = build_validation_request(extraction_result, {"document_types": ["x"]})
    assert built["extraction_id"] == "e1"
    assert built["transaction_candidates"] == [{"amount": 10}]
    assert built["active_recognition_context"] == {"document_types": ["x"]}
    assert built["document_recognition_suggestion_status"] == "none"
