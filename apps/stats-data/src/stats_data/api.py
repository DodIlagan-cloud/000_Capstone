"""M9 - Stats Data and Persistence Start
Exposes the Stats Data persistence API.
M9 End"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from stats_data.database import open_azure_sql_connection
from stats_data.duplicate_checks import check_validation_duplicates
from stats_data.processing_jobs import (
    append_processing_step,
    create_processing_job,
    get_processing_job,
    list_processing_steps,
    update_processing_job,
)
from stats_data.validation_persistence import (
    delete_uploaded_document_records,
    list_recent_uploaded_documents,
    persist_validation_result_with_temp_handoff,
    table_counts,
)


LOGGER = logging.getLogger(__name__)


class SaveTransactionsBatchRequest(BaseModel):
    validation_result: dict[str, Any] = Field(..., description="Data Validation result payload to persist.")
    uploaded_by_user_id: str | None = None
    saved_by_user_id: str | None = None
    user_email: str | None = None
    storage_reference: str | None = None
    processing_job_id: str | None = None


class DuplicateCheckRequest(BaseModel):
    validation_result: dict[str, Any] = Field(..., description="Reviewed Data Validation result payload to check before save.")
    uploaded_by_user_id: str | None = None
    saved_by_user_id: str | None = None
    user_email: str | None = None
    storage_reference: str | None = None
    processing_job_id: str | None = None


class DuplicateCheckResponse(BaseModel):
    status: str
    duplicate_check_id: str
    validation_id: str
    document_id: str
    summary: dict[str, int]
    document_results: list[dict[str, Any]]
    transaction_results: list[dict[str, Any]]


class CreateProcessingJobRequest(BaseModel):
    ingestion_id: str | None = None
    uploaded_by_user_id: str | None = None
    original_filename: str
    source_type: str = "manual_upload"
    source_id: str | None = None
    sha256: str | None = None
    message: str | None = None


class UpdateProcessingJobRequest(BaseModel):
    status: str | None = None
    stage: str | None = None
    message: str | None = None
    parse_id: str | None = None
    extraction_id: str | None = None
    validation_id: str | None = None
    result_payload: dict[str, Any] | None = None
    error_detail: str | None = None


class CreateProcessingStepRequest(BaseModel):
    module_name: str
    step_name: str
    status: str
    started_at_utc: str
    completed_at_utc: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    document_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


class ProcessingJobResponse(BaseModel):
    job_id: str
    ingestion_id: str | None = None
    uploaded_by_user_id: str | None = None
    original_filename: str
    source_type: str
    source_id: str | None = None
    sha256: str | None = None
    status: str
    stage: str
    message: str | None = None
    parse_id: str | None = None
    extraction_id: str | None = None
    validation_id: str | None = None
    result_payload: dict[str, Any] | None = None
    error_detail: str | None = None
    created_at_utc: str | None = None
    updated_at_utc: str | None = None
    completed_at_utc: str | None = None


class ProcessingStepResponse(BaseModel):
    step_id: str
    job_id: str
    document_id: str | None = None
    correlation_id: str | None = None
    module_name: str
    step_name: str
    status: str
    started_at_utc: str
    completed_at_utc: str | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at_utc: str | None = None


class ProcessingStepsResponse(BaseModel):
    steps: list[ProcessingStepResponse]


class SaveTransactionsBatchResponse(BaseModel):
    status: str
    validation_id: str
    validation_result_id: str
    document_id: str
    transaction_batch_id: str | None = None
    saved_record_count: int
    duplicate_record_count: int
    warning_record_count: int
    invalid_record_count: int
    review_item_count: int
    persisted_counts: dict[str, int]


class DeleteUploadedDocumentResponse(BaseModel):
    status: str
    document_id: str
    validation_result_id: str | None = None
    deleted_counts: dict[str, int]


class UploadedDocumentSummaryResponse(BaseModel):
    document_id: str
    original_filename: str
    document_type: str | None = None
    status: str
    source_institution: str | None = None
    created_at_utc: str | None = None
    updated_at_utc: str | None = None
    uploaded_by_user_id: str | None = None
    storage_reference: str | None = None
    validation_result_id: str | None = None
    transaction_count: int
    financial_field_count: int
    review_item_count: int


class UploadedDocumentsResponse(BaseModel):
    documents: list[UploadedDocumentSummaryResponse]


app = FastAPI(title="Stats Data API", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "service": "Stats Data API"}


@app.post("/api/v1/processing-jobs", response_model=ProcessingJobResponse)
def create_upload_processing_job(request: CreateProcessingJobRequest) -> ProcessingJobResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            job = create_processing_job(
                connection,
                ingestion_id=request.ingestion_id,
                uploaded_by_user_id=request.uploaded_by_user_id,
                original_filename=request.original_filename,
                source_type=request.source_type,
                source_id=request.source_id,
                sha256=request.sha256,
                message=request.message,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data processing job create failed.") from exc

    return ProcessingJobResponse(**job.__dict__)


@app.patch("/api/v1/processing-jobs/{job_id}", response_model=ProcessingJobResponse)
def update_upload_processing_job(job_id: str, request: UpdateProcessingJobRequest) -> ProcessingJobResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            job = update_processing_job(
                connection,
                job_id,
                status=request.status,
                stage=request.stage,
                message=request.message,
                parse_id=request.parse_id,
                extraction_id=request.extraction_id,
                validation_id=request.validation_id,
                result_payload=request.result_payload,
                error_detail=request.error_detail,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data processing job update failed.") from exc

    return ProcessingJobResponse(**job.__dict__)


@app.get("/api/v1/processing-jobs/{job_id}", response_model=ProcessingJobResponse)
def get_upload_processing_job(job_id: str) -> ProcessingJobResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            job = get_processing_job(connection, job_id)
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data processing job read failed.") from exc

    return ProcessingJobResponse(**job.__dict__)


@app.post("/api/v1/processing-jobs/{job_id}/steps", response_model=ProcessingStepResponse)
def append_upload_processing_step(job_id: str, request: CreateProcessingStepRequest) -> ProcessingStepResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            step = append_processing_step(
                connection,
                job_id,
                module_name=request.module_name,
                step_name=request.step_name,
                status=request.status,
                started_at_utc=request.started_at_utc,
                completed_at_utc=request.completed_at_utc,
                duration_ms=request.duration_ms,
                document_id=request.document_id,
                correlation_id=request.correlation_id,
                metadata=request.metadata,
                error_code=request.error_code,
                error_message=request.error_message,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data processing step append failed.") from exc

    return ProcessingStepResponse(**step.__dict__)


@app.get("/api/v1/processing-jobs/{job_id}/steps", response_model=ProcessingStepsResponse)
def list_upload_processing_steps(job_id: str) -> ProcessingStepsResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            steps = list_processing_steps(connection, job_id)
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data processing step list failed.") from exc

    return ProcessingStepsResponse(steps=[ProcessingStepResponse(**step.__dict__) for step in steps])


@app.post("/api/v1/transactions/batches", response_model=SaveTransactionsBatchResponse)
def save_transactions_batch(request: SaveTransactionsBatchRequest) -> SaveTransactionsBatchResponse:
    result = dict(request.validation_result)
    summary = result.get("summary") or {}
    step_started_at = _utc_now_iso()
    step_timer = perf_counter()

    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            plan = persist_validation_result_with_temp_handoff(
                connection,
                result,
                uploaded_by_user_id=request.uploaded_by_user_id,
                saved_by_user_id=request.saved_by_user_id,
                storage_reference=request.storage_reference,
            )
            _append_api_step(
                connection,
                request.processing_job_id,
                module_name="M9",
                step_name="database_save",
                status="completed",
                started_at_utc=step_started_at,
                started_timer=step_timer,
                metadata={
                    "validation_id": plan.validation_id,
                    "validation_result_id": plan.validation_result_id,
                    "document_id": plan.document_id,
                    "saved_record_count": int(summary.get("valid_record_count") or 0),
                    "warning_record_count": int(summary.get("warning_record_count") or 0),
                    "invalid_record_count": int(summary.get("invalid_record_count") or 0),
                },
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data persistence failed.") from exc

    persisted_counts = table_counts(plan.operations)
    batch_operation = next((operation for operation in plan.operations if operation.table == "transaction_batches"), None)
    return SaveTransactionsBatchResponse(
        status="saved",
        validation_id=plan.validation_id,
        validation_result_id=plan.validation_result_id,
        document_id=plan.document_id,
        transaction_batch_id=batch_operation.values["transaction_batch_id"] if batch_operation else None,
        saved_record_count=int(summary.get("valid_record_count") or 0),
        duplicate_record_count=int(summary.get("duplicate_record_count") or 0),
        warning_record_count=int(summary.get("warning_record_count") or 0),
        invalid_record_count=int(summary.get("invalid_record_count") or 0),
        review_item_count=int(summary.get("review_item_count") or 0),
        persisted_counts=persisted_counts,
    )


@app.post("/api/v1/transactions/duplicate-checks", response_model=DuplicateCheckResponse)
def check_transaction_duplicates(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    result = dict(request.validation_result)
    step_started_at = _utc_now_iso()
    step_timer = perf_counter()

    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            check_result = check_validation_duplicates(
                connection,
                result,
                uploaded_by_user_id=request.uploaded_by_user_id,
                saved_by_user_id=request.saved_by_user_id,
                storage_reference=request.storage_reference,
            )
            _append_api_step(
                connection,
                request.processing_job_id,
                module_name="M9",
                step_name="duplicate_check",
                status=check_result.status,
                started_at_utc=step_started_at,
                started_timer=step_timer,
                metadata={
                    "duplicate_check_id": check_result.duplicate_check_id,
                    "validation_id": check_result.validation_id,
                    "document_id": check_result.document_id,
                    "summary": check_result.summary,
                },
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data duplicate check failed.") from exc

    return DuplicateCheckResponse(
        status=check_result.status,
        duplicate_check_id=check_result.duplicate_check_id,
        validation_id=check_result.validation_id,
        document_id=check_result.document_id,
        summary=check_result.summary,
        document_results=check_result.document_results,
        transaction_results=check_result.transaction_results,
    )


@app.get("/api/v1/documents", response_model=UploadedDocumentsResponse)
def recent_uploaded_documents(limit: int = 25) -> UploadedDocumentsResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            documents = list_recent_uploaded_documents(connection, limit=limit)
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data document list failed.") from exc

    return UploadedDocumentsResponse(documents=[UploadedDocumentSummaryResponse(**document.__dict__) for document in documents])


@app.delete("/api/v1/documents/{document_id}", response_model=DeleteUploadedDocumentResponse)
def delete_uploaded_document(document_id: str) -> DeleteUploadedDocumentResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            result = delete_uploaded_document_records(connection, document_id)
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data document delete failed.") from exc

    if result.deleted_counts.get("stats_documents", 0) == 0:
        raise HTTPException(status_code=404, detail="Document was not found.")

    return DeleteUploadedDocumentResponse(
        status="deleted",
        document_id=result.document_id,
        validation_result_id=result.validation_result_id,
        deleted_counts=result.deleted_counts,
    )


def _append_api_step(
    connection: Any,
    job_id: str | None,
    *,
    module_name: str,
    step_name: str,
    status: str,
    started_at_utc: str,
    started_timer: float,
    metadata: dict[str, Any],
) -> None:
    if not job_id:
        return
    try:
        append_processing_step(
            connection,
            job_id,
            module_name=module_name,
            step_name=step_name,
            status=status,
            started_at_utc=started_at_utc,
            completed_at_utc=_utc_now_iso(),
            duration_ms=int((perf_counter() - started_timer) * 1000),
            metadata=metadata,
        )
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        LOGGER.warning(
            "Could not append processing-step timing for job_id=%s module=%s step=%s.",
            job_id,
            module_name,
            step_name,
            exc_info=True,
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
