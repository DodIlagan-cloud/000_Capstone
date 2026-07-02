"""M12 - Email Ingestion Module Start
Tests for the "ingest imported files to database" action (process_imported_run).

Uses the memory run-history store plus a fake clients object, so the real
orchestrator runs through parse -> ... -> save without httpx or a live network.
M12 End"""

from app.models.ingestion import (
    AttachmentStatus,
    EmailIngestionRunCandidate,
    EmailIngestionRunDetail,
    EmailIngestionStatus,
    EmailIngestionSummary,
)
from app.services import run_history_service
from app.services.pipeline_runner import process_imported_run


def _summary(**overrides):
    base = dict(
        message_count=1,
        attachment_count=1,
        retrieved_count=0,
        skipped_count=0,
        duplicate_count=0,
        failed_count=0,
        handed_off_count=1,
    )
    base.update(overrides)
    return EmailIngestionSummary(**base)


def _record_run_with_imported(source_id="mailbox-primary", run_id="email_run_1", ingestion_id=None):
    ingestion_id = ingestion_id or f"ing-{run_id}"
    candidate = EmailIngestionRunCandidate(
        candidate_id="cand-1",
        filename="statement.pdf",
        status=AttachmentStatus.handed_off,
        sender="statements@example.test",
        message_id="msg-1",
        attachment_id="att-1",
        sha256="abc",
        dedup_key="mailbox-primary:msg-1:att-1:abc",
        handoff_ingestion_id=ingestion_id,
        handoff_status="queued",
        handoff_content_reference=f"blob://intake/{ingestion_id}",
    )
    run_history_service.record_run(
        EmailIngestionRunDetail(
            run_id=run_id,
            source_id=source_id,
            mode="handoff",
            status=EmailIngestionStatus.completed,
            correlation_id="email_corr_1",
            summary=_summary(),
            candidates=[candidate],
        )
    )


class FakeClients:
    def __init__(self, save=None, fail=False):
        self.fetched = []
        self.saved_requests = []
        self._save = save or {"document_id": "doc-1", "saved_record_count": 2, "review_item_count": 1}
        self._fail = fail

    def fetch_content(self, request):
        self.fetched.append(request.ingestion_id)
        return b"%PDF-1.4 stored bytes"

    def create_job(self, request):
        return "job-1"

    def update_job(self, job_id, **fields):
        pass

    def parse(self, content, request):
        assert content == b"%PDF-1.4 stored bytes"
        if self._fail:
            return {"parse_id": "p1", "status": "failed"}
        return {"parse_id": "p1", "status": "completed"}

    def extract(self, parse_result):
        return {"extraction_id": "e1"}

    def fetch_recognition_context(self):
        return {}

    def validate(self, extraction_result, recognition_context):
        return {"validation_id": "v1"}

    def save(self, validation_result, request, job_id):
        self.saved_requests.append(request)
        return self._save


def test_process_imported_runs_pipeline_and_saves(clear_email_sources):
    _record_run_with_imported(run_id="email_run_save")
    clients = FakeClients()

    result = process_imported_run("mailbox-primary", clients=clients)

    assert result.status == "completed"
    assert result.processed_count == 1
    assert result.succeeded_count == 1
    assert result.saved_record_count == 2
    assert result.review_item_count == 1
    assert clients.fetched == ["ing-email_run_save"]  # bytes were read back from intake
    assert result.results[0].document_id == "doc-1"
    # Blob provenance flows into the M9 save so stats_documents.storage_reference
    # can prove which imported Blob object the database row came from.
    assert clients.saved_requests[0].storage_reference == "blob://intake/ing-email_run_save"


def test_process_imported_is_idempotent_across_repeated_runs(clear_email_sources):
    _record_run_with_imported(run_id="email_run_idempotent")
    first = process_imported_run("mailbox-primary", clients=FakeClients())
    assert first.succeeded_count == 1

    # Clicking "Ingest to database" again must not save the same attachment twice.
    second_clients = FakeClients()
    second = process_imported_run("mailbox-primary", clients=second_clients)
    assert second.status == "already_processed"
    assert second.already_processed_count == 1
    assert second.succeeded_count == 0
    assert second_clients.fetched == []  # not re-fetched, not re-saved


def test_process_imported_uses_explicit_import_run_not_latest_run(clear_email_sources):
    _record_run_with_imported(run_id="email_run_import", ingestion_id="ing-imported")
    run_history_service.record_run(
        EmailIngestionRunDetail(
            run_id="email_run_newer_dry_run",
            source_id="mailbox-primary",
            mode="dry_run",
            status=EmailIngestionStatus.completed,
            summary=_summary(handed_off_count=0),
            candidates=[
                EmailIngestionRunCandidate(
                    candidate_id="dry-candidate",
                    filename="dry.pdf",
                    status=AttachmentStatus.retrieved,
                )
            ],
        )
    )
    clients = FakeClients()

    result = process_imported_run("mailbox-primary", run_id="email_run_import", clients=clients)

    assert result.status == "completed"
    assert result.run_id == "email_run_import"
    assert clients.fetched == ["ing-imported"]


def test_process_imported_rejects_run_id_from_another_source(clear_email_sources):
    _record_run_with_imported(source_id="other-mailbox", run_id="email_run_other", ingestion_id="ing-other")

    result = process_imported_run("mailbox-primary", run_id="email_run_other", clients=FakeClients())

    assert result.status == "not_found"


def test_process_imported_reports_failure_per_candidate(clear_email_sources):
    _record_run_with_imported(run_id="email_run_failure")
    clients = FakeClients(fail=True)

    result = process_imported_run("mailbox-primary", clients=clients)

    assert result.status == "failed"
    assert result.failed_count == 1
    assert result.results[0].status == "failed"


def test_process_imported_no_run_returns_not_found(clear_email_sources):
    result = process_imported_run("unknown-source", clients=FakeClients())
    assert result.status == "not_found"


def test_process_imported_run_without_handed_off_files(clear_email_sources):
    run_history_service.record_run(
        EmailIngestionRunDetail(
            run_id="email_run_dry",
            source_id="mailbox-primary",
            mode="dry_run",
            status=EmailIngestionStatus.completed,
            summary=_summary(handed_off_count=0),
            candidates=[
                EmailIngestionRunCandidate(
                    candidate_id="c2",
                    filename="x.pdf",
                    status=AttachmentStatus.retrieved,
                )
            ],
        )
    )
    result = process_imported_run("mailbox-primary", clients=FakeClients())
    assert result.status == "no_imported_files"


def test_process_imported_reports_configuration_failure_counts(clear_email_sources, monkeypatch):
    _record_run_with_imported(run_id="email_run_config_error")

    class BrokenPipelineClients:
        def __init__(self, _settings):
            raise RuntimeError("STATS_INTERNAL_API_KEY is required for automated database ingestion.")

    monkeypatch.setitem(process_imported_run.__globals__, "PipelineClients", BrokenPipelineClients)

    result = process_imported_run("mailbox-primary")

    assert result.status == "failed"
    assert result.processed_count == 1
    assert result.failed_count == 1
    assert result.results[0].status == "failed"
    assert "STATS_INTERNAL_API_KEY" in result.results[0].error
