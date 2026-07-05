"""M9 - Stats Data and Persistence Start
Exposes the Stats Data persistence API.
M9 End"""

from __future__ import annotations

import logging
import hmac
import os
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from stats_data.database import open_azure_sql_connection
from stats_data.duplicate_checks import check_validation_duplicates
from stats_data.merchant_learning import lookup_merchant_classification
from stats_data.processing_jobs import (
    append_processing_step,
    create_processing_job,
    get_processing_job,
    list_processing_steps,
    update_processing_job,
)
from stats_data.recognition_settings import (
    active_recognition_settings,
    delete_label,
    delete_rule,
    review_suggestion,
    save_label,
    save_rule,
)
from stats_data.validation_persistence import (
    delete_uploaded_document_records,
    list_recent_uploaded_documents,
    persist_validation_result_with_temp_handoff,
    table_counts,
)
from stats_data.reporting_queries import (
    TransactionFilters,
    fetch_document_detail,
    fetch_document_provenance,
    fetch_findings,
    fetch_review_items,
    fetch_transactions,
    summarize_document_rows,
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


class RecognitionSuggestionResponse(BaseModel):
    suggestion_id: str
    source_module: str
    suggestion_status: str
    document_id: str | None = None
    transaction_id: str | None = None
    source_candidate_id: str | None = None
    current_document_type: str | None = None
    current_document_subtype: str | None = None
    current_transaction_type: str | None = None
    current_transaction_subtype: str | None = None
    current_spending_category: str | None = None
    current_spending_subcategory: str | None = None
    suggested_document_type: str | None = None
    suggested_document_subtype: str | None = None
    suggested_transaction_type: str | None = None
    suggested_transaction_subtype: str | None = None
    suggested_spending_category: str | None = None
    suggested_spending_subcategory: str | None = None
    suggestion_confidence: float | None = None
    suggestion_source: str | None = None
    suggestion_evidence_ref: str | None = None
    created_at_utc: str | None = None
    reviewed_at_utc: str | None = None
    review_action: str | None = None


class RecognitionSuggestionsResponse(BaseModel):
    suggestions: list[RecognitionSuggestionResponse]


class RecognitionSyncPreviewRequest(BaseModel):
    label_field: str
    old_value: str
    new_value: str | None = None


class RecognitionSyncPreviewResponse(BaseModel):
    label_field: str
    old_value: str
    new_value: str | None = None
    affected_row_count: int


class RecognitionLabelSaveRequest(BaseModel):
    scope: str
    original_label: str | None = None
    label: str
    values: list[str] = Field(default_factory=list)


class RecognitionLabelDeleteRequest(BaseModel):
    scope: str
    label: str


class RecognitionRuleSaveRequest(BaseModel):
    scope: str
    original_reason_code: str | None = None
    target_label: str
    target_subtype: str
    reason_code: str
    required_any: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    minimum_score: float = 0.35


class RecognitionRuleDeleteRequest(BaseModel):
    scope: str
    reason_code: str


class RecognitionSuggestionReviewRequest(BaseModel):
    action: str
    admin_user_id: str | None = None
    review_note: str | None = None


class MerchantClassificationLookupResponse(BaseModel):
    merchant_key: str
    match_status: str
    match_type: str
    merchant_display_name: str | None = None
    transaction_type: str | None = None
    transaction_subtype: str | None = None
    spending_category: str | None = None
    spending_subcategory: str | None = None
    profile_confidence: float
    confirmation_count: int
    conflict_count: int
    profile_status: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


app = FastAPI(title="Stats Data API", version="1.0.0")
INTERNAL_ADMIN_HEADER = "X-Stats-Internal-Key"


def _require_internal_admin_key(
    x_stats_internal_key: str | None = Header(default=None, alias=INTERNAL_ADMIN_HEADER),
) -> bool:
    expected = os.environ.get("STATS_INTERNAL_API_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Stats internal API key is not configured.")
    if not x_stats_internal_key or not hmac.compare_digest(x_stats_internal_key, expected):
        raise HTTPException(status_code=403, detail="Stats internal API key is required.")
    return True


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
def save_transactions_batch(
    request: SaveTransactionsBatchRequest,
    x_stats_user_id: str | None = Header(default=None, alias="X-Stats-User-Id"),
) -> SaveTransactionsBatchResponse:
    result = dict(request.validation_result)
    # P2-2: the trusted proxy identity is authoritative for ownership. When present
    # it overrides any client-supplied owner id so records cannot be saved under
    # another user's account; internal callers without the header keep body values.
    trusted_user_id = (x_stats_user_id or "").strip() or None
    owner_user_id = trusted_user_id or request.uploaded_by_user_id
    saved_by_user_id = trusted_user_id or request.saved_by_user_id
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
                uploaded_by_user_id=owner_user_id,
                saved_by_user_id=saved_by_user_id,
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
def check_transaction_duplicates(
    request: DuplicateCheckRequest,
    x_stats_user_id: str | None = Header(default=None, alias="X-Stats-User-Id"),
) -> DuplicateCheckResponse:
    result = dict(request.validation_result)
    trusted_user_id = (x_stats_user_id or "").strip() or None
    owner_user_id = trusted_user_id or request.uploaded_by_user_id
    saved_by_user_id = trusted_user_id or request.saved_by_user_id
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
                uploaded_by_user_id=owner_user_id,
                saved_by_user_id=saved_by_user_id,
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


def require_user_id(
    x_stats_user_id: str | None = Header(default=None, alias="X-Stats-User-Id"),
) -> str:
    """Resolve the authenticated user id from the trusted proxy identity header.

    Stats Web resolves the signed-in user and injects ``X-Stats-User-Id`` after
    stripping any client-supplied copy, so this value is trusted for scoping.
    """
    user_id = (x_stats_user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing authenticated user context.")
    return user_id


def require_admin_flag(
    x_stats_user_role: str | None = Header(default=None, alias="X-Stats-User-Role"),
) -> bool:
    """Read the trusted role header the proxy injects. Admins get role-aware
    cross-user visibility (spec: Security And Data Governance), which also keeps
    legacy rows with a NULL owner visible to administrators (P2-3)."""
    return (x_stats_user_role or "").strip().lower() == "admin"


def _query_read_model(runner) -> Any:
    """Open a connection, run a user-scoped read, and always close it."""
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        try:
            return runner(connection)
        finally:
            connection.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data reporting query failed.") from exc


@app.get("/api/v1/documents", response_model=UploadedDocumentsResponse)
def recent_uploaded_documents(
    limit: int = 25,
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
) -> UploadedDocumentsResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            documents = list_recent_uploaded_documents(
                connection, limit=limit, owner_user_id=None if is_admin else user_id
            )
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stats Data document list failed.") from exc

    return UploadedDocumentsResponse(documents=[UploadedDocumentSummaryResponse(**document.__dict__) for document in documents])


@app.get("/api/v1/transactions")
def list_transactions(
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
    currency: str | None = None,
    direction: str | None = None,
    transaction_type: str | None = None,
    transaction_subtype: str | None = None,
    spending_category: str | None = None,
    spending_subcategory: str | None = None,
    merchant: str | None = None,
    source_institution: str | None = None,
    payment_method: str | None = None,
    quality_status: str | None = None,
    classification_source: str | None = None,
    review_required: bool | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    filters = TransactionFilters(
        currency=currency,
        direction=direction,
        transaction_type=transaction_type,
        transaction_subtype=transaction_subtype,
        spending_category=spending_category,
        spending_subcategory=spending_subcategory,
        merchant=merchant,
        source_institution=source_institution,
        payment_method=payment_method,
        quality_status=quality_status,
        classification_source=classification_source,
        review_required=review_required,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    rows = _query_read_model(lambda conn: fetch_transactions(conn, user_id, filters, include_all=is_admin))
    return {"items": rows, "count": len(rows)}


@app.get("/api/v1/documents/summary")
def documents_summary(
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
) -> dict[str, Any]:
    rows = _query_read_model(lambda conn: fetch_document_provenance(conn, user_id, include_all=is_admin))
    return {"summary": summarize_document_rows(rows), "documents": rows}


@app.get("/api/v1/documents/{document_id}")
def document_detail(
    document_id: str,
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
) -> dict[str, Any]:
    document = _query_read_model(
        lambda conn: fetch_document_detail(conn, user_id, document_id, include_all=is_admin)
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"document": document}


@app.get("/api/v1/review-items")
def list_review_items(
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _query_read_model(
        lambda conn: fetch_review_items(
            conn, user_id, status=status, severity=severity, limit=limit, offset=offset, include_all=is_admin
        )
    )
    return {"items": rows, "count": len(rows)}


@app.get("/api/v1/findings")
def list_findings(
    user_id: str = Depends(require_user_id),
    is_admin: bool = Depends(require_admin_flag),
    status: str | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    rows = _query_read_model(
        lambda conn: fetch_findings(
            conn, user_id, status=status, severity=severity, limit=limit, offset=offset, include_all=is_admin
        )
    )
    return {"items": rows, "count": len(rows)}


@app.get("/api/v1/admin/recognition-settings/suggestions", response_model=RecognitionSuggestionsResponse)
def recognition_label_suggestions(
    status: str = "pending",
    limit: int = 50,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> RecognitionSuggestionsResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            cursor = connection.cursor()
            cursor.execute(
                """
SELECT TOP (?) suggestion_id, source_module, suggestion_status, document_id, transaction_id,
       source_candidate_id, current_document_type, current_document_subtype,
       current_transaction_type, current_transaction_subtype,
       current_spending_category, current_spending_subcategory, suggested_transaction_type,
       suggested_transaction_subtype, suggested_spending_category, suggested_spending_subcategory,
       suggested_document_type, suggested_document_subtype,
       suggestion_confidence, suggestion_source, suggestion_evidence_ref, created_at_utc,
       reviewed_at_utc, review_action
FROM dbo.recognition_label_suggestions
WHERE (? = 'all' OR suggestion_status = ?)
ORDER BY created_at_utc DESC;
""",
                max(1, min(limit, 200)),
                status,
                status,
            )
            suggestions = [_row_dict(cursor, row) for row in cursor.fetchall()]
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition label suggestions could not be loaded.") from exc

    return RecognitionSuggestionsResponse(
        suggestions=[RecognitionSuggestionResponse(**suggestion) for suggestion in suggestions]
    )


@app.get("/api/v1/admin/recognition-settings/active")
def recognition_settings_active(
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, Any]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            return active_recognition_settings(connection)
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Active recognition settings could not be loaded.") from exc


@app.get("/api/v1/internal/merchant-classifications/lookup", response_model=MerchantClassificationLookupResponse)
def merchant_classification_lookup(
    description: str,
    owner_user_id: str | None = None,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> MerchantClassificationLookupResponse:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            lookup = lookup_merchant_classification(
                connection,
                description=description,
                owner_user_id=owner_user_id,
            )
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Merchant classification lookup failed.") from exc

    return MerchantClassificationLookupResponse(
        merchant_key=lookup.merchant_key,
        match_status=lookup.match_status,
        match_type=lookup.match_type,
        merchant_display_name=lookup.merchant_display_name,
        transaction_type=lookup.transaction_type,
        transaction_subtype=lookup.transaction_subtype,
        spending_category=lookup.spending_category,
        spending_subcategory=lookup.spending_subcategory,
        profile_confidence=lookup.profile_confidence,
        confirmation_count=lookup.confirmation_count,
        conflict_count=lookup.conflict_count,
        profile_status=lookup.profile_status,
        reason_codes=lookup.reason_codes or [],
    )


@app.patch("/api/v1/admin/recognition-settings/suggestions/{suggestion_id}")
def recognition_suggestion_review(
    suggestion_id: str,
    request: RecognitionSuggestionReviewRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, Any]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            return review_suggestion(
                connection,
                suggestion_id=suggestion_id,
                action=request.action,
                admin_user_id=request.admin_user_id,
                review_note=request.review_note,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition suggestion could not be reviewed.") from exc


@app.post("/api/v1/admin/recognition-settings/labels")
def recognition_label_save(
    request: RecognitionLabelSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            save_label(
                connection,
                scope=request.scope,
                original_label=request.original_label or "",
                label=request.label,
                values=request.values,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition label could not be saved.") from exc

    return {"status": "saved"}


@app.post("/api/v1/admin/recognition-settings/document-labels")
@app.patch("/api/v1/admin/recognition-settings/document-labels")
def recognition_document_label_save(
    request: RecognitionLabelSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "document"
    return recognition_label_save(request, True)


@app.post("/api/v1/admin/recognition-settings/transaction-labels")
@app.patch("/api/v1/admin/recognition-settings/transaction-labels")
def recognition_transaction_label_save(
    request: RecognitionLabelSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "transaction"
    return recognition_label_save(request, True)


@app.post("/api/v1/admin/recognition-settings/spending-labels")
@app.patch("/api/v1/admin/recognition-settings/spending-labels")
def recognition_spending_label_save(
    request: RecognitionLabelSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "spending"
    return recognition_label_save(request, True)


@app.delete("/api/v1/admin/recognition-settings/labels")
def recognition_label_delete(
    request: RecognitionLabelDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            delete_label(connection, scope=request.scope, label=request.label)
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition label could not be deleted.") from exc

    return {"status": "deleted"}


@app.delete("/api/v1/admin/recognition-settings/document-labels")
def recognition_document_label_delete(
    request: RecognitionLabelDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "document"
    return recognition_label_delete(request, True)


@app.delete("/api/v1/admin/recognition-settings/transaction-labels")
def recognition_transaction_label_delete(
    request: RecognitionLabelDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "transaction"
    return recognition_label_delete(request, True)


@app.delete("/api/v1/admin/recognition-settings/spending-labels")
def recognition_spending_label_delete(
    request: RecognitionLabelDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "spending"
    return recognition_label_delete(request, True)


@app.post("/api/v1/admin/recognition-settings/rules")
def recognition_rule_save(
    request: RecognitionRuleSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            save_rule(
                connection,
                scope=request.scope,
                original_reason_code=request.original_reason_code or "",
                target_label=request.target_label,
                target_subtype=request.target_subtype,
                reason_code=request.reason_code,
                required_any=request.required_any,
                signals=request.signals,
                minimum_score=request.minimum_score,
            )
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition rule could not be saved.") from exc

    return {"status": "saved"}


@app.post("/api/v1/admin/recognition-settings/document-rules")
@app.patch("/api/v1/admin/recognition-settings/document-rules")
def recognition_document_rule_save(
    request: RecognitionRuleSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "document"
    return recognition_rule_save(request, True)


@app.post("/api/v1/admin/recognition-settings/transaction-rules")
@app.patch("/api/v1/admin/recognition-settings/transaction-rules")
def recognition_transaction_rule_save(
    request: RecognitionRuleSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "transaction"
    return recognition_rule_save(request, True)


@app.post("/api/v1/admin/recognition-settings/spending-rules")
@app.patch("/api/v1/admin/recognition-settings/spending-rules")
def recognition_spending_rule_save(
    request: RecognitionRuleSaveRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "spending"
    return recognition_rule_save(request, True)


@app.delete("/api/v1/admin/recognition-settings/rules")
def recognition_rule_delete(
    request: RecognitionRuleDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            delete_rule(connection, scope=request.scope, reason_code=request.reason_code)
        finally:
            connection.close()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition rule could not be deleted.") from exc

    return {"status": "deleted"}


@app.delete("/api/v1/admin/recognition-settings/document-rules")
def recognition_document_rule_delete(
    request: RecognitionRuleDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "document"
    return recognition_rule_delete(request, True)


@app.delete("/api/v1/admin/recognition-settings/transaction-rules")
def recognition_transaction_rule_delete(
    request: RecognitionRuleDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "transaction"
    return recognition_rule_delete(request, True)


@app.delete("/api/v1/admin/recognition-settings/spending-rules")
def recognition_spending_rule_delete(
    request: RecognitionRuleDeleteRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> dict[str, str]:
    request.scope = "spending"
    return recognition_rule_delete(request, True)


@app.post("/api/v1/admin/recognition-settings/sync-preview", response_model=RecognitionSyncPreviewResponse)
def recognition_label_sync_preview(
    request: RecognitionSyncPreviewRequest,
    _authorized: bool = Depends(_require_internal_admin_key),
) -> RecognitionSyncPreviewResponse:
    allowed_fields = {
        "transaction_type",
        "transaction_subtype",
        "spending_category",
        "spending_subcategory",
    }
    if request.label_field not in allowed_fields:
        raise HTTPException(status_code=400, detail="Unsupported recognition label field.")

    try:
        connection = open_azure_sql_connection()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        try:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT COUNT(1) AS affected_row_count FROM dbo.transactions WHERE {request.label_field} = ?;",
                request.old_value,
            )
            row = cursor.fetchone()
            affected_count = int(row[0] if row else 0)
        finally:
            connection.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Recognition label sync preview failed.") from exc

    return RecognitionSyncPreviewResponse(
        label_field=request.label_field,
        old_value=request.old_value,
        new_value=request.new_value,
        affected_row_count=affected_count,
    )


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


def _row_dict(cursor: Any, row: Any) -> dict[str, Any]:
    columns = [column[0] for column in cursor.description]
    values = {}
    for index, column in enumerate(columns):
        value = row[index]
        if isinstance(value, datetime):
            values[column] = value.isoformat().replace("+00:00", "Z")
        else:
            values[column] = value
    return values
