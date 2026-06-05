"""M9 - Stats Data and Persistence Start
Exposes the Stats Data persistence API.
M9 End"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from stats_data.database import open_azure_sql_connection
from stats_data.validation_persistence import (
    delete_uploaded_document_records,
    list_recent_uploaded_documents,
    persist_validation_result_with_temp_handoff,
    table_counts,
)


class SaveTransactionsBatchRequest(BaseModel):
    validation_result: dict[str, Any] = Field(..., description="Data Validation result payload to persist.")
    uploaded_by_user_id: str | None = None
    saved_by_user_id: str | None = None
    user_email: str | None = None
    storage_reference: str | None = None


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


@app.post("/api/v1/transactions/batches", response_model=SaveTransactionsBatchResponse)
def save_transactions_batch(request: SaveTransactionsBatchRequest) -> SaveTransactionsBatchResponse:
    result = dict(request.validation_result)
    summary = result.get("summary") or {}

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
