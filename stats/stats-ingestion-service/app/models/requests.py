"""Pydantic request and response models."""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import date as Date
from datetime import datetime

from app.models.common import ErrorResponse


class TransactionResponse(BaseModel):
    """Response model for extracted transaction."""

    model_config = ConfigDict(from_attributes=True)
    
    date: Date = Field(..., description="Transaction date")
    description: str = Field(..., description="Transaction description")
    amount: float = Field(..., description="Transaction amount")
    transaction_type: str = Field(..., description="Transaction type: credit or debit")
    reference: Optional[str] = Field(None, description="Transaction reference number")


class IngestResponse(BaseModel):
    """Response model for PDF ingestion."""
    
    status: str = Field(..., description="Status of ingestion")
    upload_id: str = Field(..., description="Unique upload identifier")
    filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    document_type: str = Field(..., description="Detected document type")
    page_count: int = Field(..., description="Number of pages in PDF")
    transactions: List[TransactionResponse] = Field(..., description="Extracted transactions")
    transaction_count: int = Field(..., description="Number of transactions extracted")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    upload_timestamp: datetime = Field(..., description="When the file was uploaded")


class PDFDocumentResponse(BaseModel):
    """Response model for a stored PDF document."""

    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="Document ID")
    upload_id: str = Field(..., description="Unique upload identifier")
    filename: str = Field(..., description="Original filename")
    file_size_bytes: int = Field(..., description="File size in bytes")
    document_type: str = Field(..., description="Detected document type")
    processing_status: str = Field(..., description="Processing status")
    page_count: int = Field(..., description="Number of pages")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")
    upload_timestamp: datetime = Field(..., description="When the file was uploaded")
    
class PDFListResponse(BaseModel):
    """Response model for list of PDFs."""
    
    total: int = Field(..., description="Total number of PDFs")
    items: List[PDFDocumentResponse] = Field(..., description="List of PDFs")


class TransactionListResponse(BaseModel):
    """Response model for list of transactions."""
    
    pdf_upload_id: str = Field(..., description="Upload ID of the PDF")
    total: int = Field(..., description="Total number of transactions")
    items: List[TransactionResponse] = Field(..., description="List of transactions")
