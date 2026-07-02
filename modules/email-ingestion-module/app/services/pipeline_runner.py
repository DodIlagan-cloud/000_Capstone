"""M12 - Email Ingestion Module Start
Drives the automated pipeline for already-imported files.

Used by the manual "Ingest to database" button on the Email Setup page: it takes the
handed-off attachments from an import run and pushes each through
parse -> extract -> validate -> save (process-to-database via the M9 endpoint with a
system identity) by fetching the stored bytes back from intake. This is not fully
governed auto-save yet; the automated save takes the unreviewed path so M9 governs it.
The same entry point is reused by the scheduled/automated trigger.
M12 End"""

import logging

from app.models.ingestion import (
    AttachmentStatus,
    ProcessImportedCandidateResult,
    ProcessImportedResult,
)
from app.pipeline.clients import PipelineClients
from app.pipeline.config import load_settings
from app.pipeline.models import PipelineRunRequest
from app.pipeline.orchestrator import run_automated_pipeline
from app.services import run_history_service


logger = logging.getLogger(__name__)


def process_imported_run(source_id, run_id=None, *, clients=None, runner=run_automated_pipeline):
    """Run the pipeline for the handed-off attachments of an import run.

    `clients` and `runner` are injectable for testing; production builds an httpx
    `PipelineClients` from environment settings.
    """
    run = _resolve_run(source_id, run_id)
    if run is None:
        return ProcessImportedResult(run_id=run_id, source_id=source_id, status="not_found")

    imported = [
        candidate
        for candidate in run.candidates
        if candidate.status == AttachmentStatus.handed_off and candidate.handoff_ingestion_id
    ]
    if not imported:
        return ProcessImportedResult(run_id=run.run_id, source_id=run.source_id, status="no_imported_files")

    owns_clients = clients is None
    if clients is None:
        try:
            clients = PipelineClients(load_settings())
        except RuntimeError as exc:
            # Clear configuration error (e.g. missing internal key) instead of a 500.
            return ProcessImportedResult(
                run_id=run.run_id,
                source_id=run.source_id,
                status="failed",
                error=str(exc),
                processed_count=1,
                failed_count=1,
                results=[ProcessImportedCandidateResult(filename="", status="failed", error=str(exc))],
            )
    try:
        return _process_candidates(run, imported, clients, runner)
    finally:
        if owns_clients:
            clients.close()


def _process_candidates(run, imported, clients, runner) -> ProcessImportedResult:
    results: list[ProcessImportedCandidateResult] = []
    succeeded = failed = already_processed = saved_total = review_total = 0

    for candidate in imported:
        # Idempotency: an attachment that a prior process-imported (button or
        # scheduler) already pushed to M9 must not be saved again.
        if run_history_service.is_ingestion_processed(candidate.handoff_ingestion_id):
            already_processed += 1
            results.append(
                ProcessImportedCandidateResult(
                    ingestion_id=candidate.handoff_ingestion_id,
                    filename=candidate.filename,
                    status="already_processed",
                )
            )
            continue

        request = PipelineRunRequest(
            ingestion_id=candidate.handoff_ingestion_id,
            original_filename=candidate.filename,
            source_type="email_attachment",
            source_id=run.source_id,
            sha256=candidate.sha256,
            content_base64=None,  # fetched back from intake by ingestion_id
            # Blob provenance: M9 persists this into stats_documents.storage_reference,
            # so the database row can be traced back to the imported Blob object.
            storage_reference=candidate.handoff_content_reference,
            correlation_id=run.correlation_id,
        )
        outcome = runner(request, clients)
        if outcome.status == "completed":
            succeeded += 1
            run_history_service.mark_ingestion_processed(
                candidate.handoff_ingestion_id, outcome.document_id, run.run_id
            )
        else:
            failed += 1
        saved_total += outcome.saved_record_count
        review_total += outcome.review_item_count
        results.append(
            ProcessImportedCandidateResult(
                ingestion_id=candidate.handoff_ingestion_id,
                filename=candidate.filename,
                status=outcome.status,
                document_id=outcome.document_id,
                saved_record_count=outcome.saved_record_count,
                review_item_count=outcome.review_item_count,
                error=outcome.error,
            )
        )

    if failed and not succeeded:
        status = "failed"
    elif failed:
        status = "completed_with_warnings"
    elif already_processed and not succeeded:
        status = "already_processed"
    elif already_processed:
        status = "completed_with_warnings"
    else:
        status = "completed"

    logger.info(
        "M12 process-imported finished. run_id=%s source_id=%s succeeded=%s failed=%s already_processed=%s",
        run.run_id, run.source_id, succeeded, failed, already_processed,
    )
    return ProcessImportedResult(
        run_id=run.run_id,
        source_id=run.source_id,
        status=status,
        processed_count=succeeded + failed,
        succeeded_count=succeeded,
        failed_count=failed,
        already_processed_count=already_processed,
        saved_record_count=saved_total,
        review_item_count=review_total,
        results=results,
    )


def _resolve_run(source_id, run_id):
    if run_id:
        run = run_history_service.get_run(run_id)
        if run is None or run.source_id != source_id:
            return None
        return run
    summaries = run_history_service.list_runs(source_id=source_id, limit=1)
    if not summaries:
        return None
    return run_history_service.get_run(summaries[0].run_id)
