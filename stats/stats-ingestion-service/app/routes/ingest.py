"""Ingest router for PDF upload and processing."""

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, status

from app.config import settings
from app.errors import ErrorType, api_error
from app.models.requests import ErrorResponse, IngestResponse
from app.models.transaction import Transaction

router = APIRouter(tags=["Ingest"])


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def ingest_pdf(file: UploadFile = File(...)) -> IngestResponse:
    """Upload and process a PDF file to extract transactions."""
    filename = file.filename or ""

    if not filename.lower().endswith(".pdf"):
        raise api_error(ErrorType.INVALID_FILE_TYPE, "Only PDF files are allowed")

    file_content = await file.read()
    max_size_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_content) > max_size_bytes:
        raise api_error(
            ErrorType.FILE_TOO_LARGE,
            f"File size exceeds {settings.max_file_size_mb}MB limit",
        )

    try:
        upload_id = str(uuid.uuid4())
        upload_timestamp = datetime.utcnow()
        start_time = time.time()

        mock_transactions = [
            Transaction(
                date="2026-04-17",
                description="COFFEE SHOP PURCHASE",
                amount=-5.50,
                transaction_type="debit",
                reference="TXN001",
            ),
            Transaction(
                date="2026-04-16",
                description="SALARY DEPOSIT",
                amount=2500.00,
                transaction_type="credit",
                reference="TXN002",
            ),
        ]

        processing_time = (time.time() - start_time) * 1000

        return IngestResponse(
            status="success",
            upload_id=upload_id,
            filename=filename,
            file_size_bytes=len(file_content),
            document_type="bank_statement",
            page_count=0,
            transactions=mock_transactions,
            transaction_count=len(mock_transactions),
            processing_time_ms=processing_time,
            upload_timestamp=upload_timestamp,
        )
    except Exception as exc:
        raise api_error(
            ErrorType.PROCESSING_ERROR,
            f"Failed to process PDF: {exc}",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc
