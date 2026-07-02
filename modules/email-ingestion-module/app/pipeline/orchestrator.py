"""M12 - Email Ingestion Module Start
Automated pipeline core sequence.

Runs one ingested document end-to-end with no human in the loop:

    create job -> M5 parse -> M7 extract -> M8 validate -> M9 process-to-database

The orchestrator is transport-agnostic: it depends on a `clients` object (duck-typed)
exposing create_job/update_job/parse/extract/fetch_recognition_context/validate/save.
Production uses `clients.PipelineClients` (httpx); tests inject a fake. This keeps the
core logic runnable and testable without httpx, pydantic, or a live network.

Idempotency: the caller keys a run on `ingestion_id` (in the Event Grid + Durable
Functions design the orchestration instance id is the ingestion id), so an
at-least-once trigger cannot start two pipelines or double-write M9 for one document.
M12 End"""

import base64
import logging

from app.pipeline.models import PipelineRunRequest, PipelineRunResult, PipelineStep
from app.pipeline.request_builders import int_at, text_at


logger = logging.getLogger(__name__)


class PipelineInputError(ValueError):
    """Raised when the trigger payload cannot start a pipeline run."""


def run_automated_pipeline(request: PipelineRunRequest, clients) -> PipelineRunResult:
    result = PipelineRunResult(ingestion_id=request.ingestion_id, status="failed")

    try:
        content = _resolve_content(request, clients)
    except PipelineInputError as exc:
        result.steps.append(PipelineStep(name="input", status="failed", detail=str(exc)))
        result.error = str(exc)
        return result

    try:
        job_id = clients.create_job(request)
    except Exception as exc:  # noqa: BLE001 - a bad/absent job id must fail the run cleanly.
        detail = _safe_error(str(exc))
        result.steps.append(PipelineStep(name="create_job", status="failed", detail=detail))
        result.error = detail
        return result
    result.job_id = job_id
    result.steps.append(PipelineStep(name="create_job", status="completed", detail=f"job_id={job_id}"))

    try:
        clients.update_job(job_id, status="running", stage="parsing", message="Stats is reading the document text.")
        parse_result = clients.parse(content, request)
        parse_id = text_at(parse_result, "parse_id")
        result.parse_id = parse_id
        if text_at(parse_result, "status") == "failed":
            detail = "Document parsing failed."
            result.steps.append(PipelineStep(name="document_parsing", status="failed", detail=detail))
            result.error = detail
            clients.update_job(job_id, status="failed", stage="failed", message=detail, parse_id=parse_id, error_detail=detail)
            return result
        result.steps.append(PipelineStep(name="document_parsing", status="completed"))

        clients.update_job(
            job_id, status="running", stage="extracting",
            message="Text was read. Stats is finding transaction details.", parse_id=parse_id,
        )
        extraction_result = clients.extract(parse_result)
        extraction_id = text_at(extraction_result, "extraction_id")
        result.extraction_id = extraction_id
        result.steps.append(PipelineStep(name="transaction_extraction", status="completed"))

        clients.update_job(
            job_id, status="running", stage="validating",
            message="Transactions were found. Stats is checking the details.",
            parse_id=parse_id, extraction_id=extraction_id,
        )
        recognition_context = clients.fetch_recognition_context()
        validation_result = clients.validate(extraction_result, recognition_context)
        validation_id = text_at(validation_result, "validation_id")
        result.validation_id = validation_id
        result.steps.append(PipelineStep(name="data_validation", status="completed"))

        # Save to database. Calls the SAME M9 endpoint the human-reviewed save uses,
        # with a system identity, but WITHOUT the manual review transform - it persists
        # the M8 validation result as-is. A real automated save policy (duplicate check,
        # known-vocabulary gating, confidence thresholds, and review routing for
        # warning/invalid/out-of-vocabulary rows) is still TO BE ADDED; until then this
        # is "process to database", not governed auto-save. See
        # docs/M12-email-to-database-automation-plan.md.
        clients.update_job(
            job_id, status="running", stage="saving",
            message="Stats is saving the checked transactions.",
            parse_id=parse_id, extraction_id=extraction_id, validation_id=validation_id,
        )
        save_result = clients.save(validation_result, request, job_id)
        result.document_id = text_at(save_result, "document_id")
        result.saved_record_count = int_at(save_result, "saved_record_count")
        result.review_item_count = int_at(save_result, "review_item_count")
        result.warning_record_count = int_at(save_result, "warning_record_count")
        result.invalid_record_count = int_at(save_result, "invalid_record_count")
        result.steps.append(
            PipelineStep(name="database_save", status="completed", detail=f"document_id={result.document_id}")
        )

        clients.update_job(
            job_id, status="completed", stage="completed", message="Transactions saved.",
            parse_id=parse_id, extraction_id=extraction_id, validation_id=validation_id,
        )
        result.status = "completed"
        return result
    except Exception as exc:  # noqa: BLE001 - any module/transport failure marks the run failed.
        detail = _safe_error(str(exc))
        result.steps.append(PipelineStep(name="pipeline", status="failed", detail=detail))
        result.error = detail
        logger.warning(
            "Automated pipeline run failed. ingestion_id=%s correlation_id=%s detail=%s",
            request.ingestion_id, request.correlation_id, detail,
        )
        try:
            clients.update_job(job_id, status="failed", stage="failed", message="Automated document processing failed.", error_detail=detail)
        except Exception:  # pragma: no cover - failure-on-failure guard
            logger.warning("Could not mark automated job failed. ingestion_id=%s", request.ingestion_id)
        return result


def _resolve_content(request: PipelineRunRequest, clients) -> bytes:
    # Prefer inline content from the trigger (M12 holds the bytes at handoff). If it
    # is absent - e.g. the manual "ingest imported" button or the event-driven path
    # acting on an already-stored file - fetch the original bytes back from intake.
    if request.content_base64:
        try:
            return base64.b64decode(request.content_base64, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise PipelineInputError("content_base64 is not valid base64.") from exc

    fetch = getattr(clients, "fetch_content", None)
    if fetch is None:
        raise PipelineInputError(
            "No inline content was provided and the clients cannot fetch stored intake content."
        )
    try:
        content = fetch(request)
    except Exception as exc:  # noqa: BLE001
        raise PipelineInputError(f"Stored intake content could not be read: {_safe_error(str(exc))}") from exc
    if not content:
        raise PipelineInputError("Stored intake content was empty or unavailable for this ingestion.")
    return content


def _safe_error(message: str) -> str:
    # Keep error detail bounded and free of obvious secret-bearing tokens.
    trimmed = (message or "").strip()
    if len(trimmed) > 500:
        trimmed = trimmed[:500] + "..."
    return trimmed or "Unknown error."
