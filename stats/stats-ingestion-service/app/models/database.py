"""Database models for PDFs and transactions."""

from sqlalchemy import Column, Integer, String, Float, DateTime, LargeBinary, ForeignKey, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class PDFDocument(Base):
    """Model for storing PDF documents."""
    
    __tablename__ = "pdf_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(String, unique=True, index=True, nullable=False)
    filename = Column(String, nullable=False)
    file_content = Column(LargeBinary, nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    document_type = Column(String, default="unknown")  # e.g., "bank_statement", "invoice"
    processing_status = Column(String, default="pending")  # pending, completed, failed
    extraction_error = Column(Text, nullable=True)
    processing_time_ms = Column(Float, nullable=True)
    page_count = Column(Integer, nullable=True)
    
    # Relationships
    transactions = relationship("StoredTransaction", back_populates="pdf_document")
    extracted_text = relationship("ExtractedText", back_populates="pdf_document", uselist=False)
    
    class Config:
        from_attributes = True


class StoredTransaction(Base):
    """Model for storing extracted transactions."""
    
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    pdf_document_id = Column(Integer, ForeignKey("pdf_documents.id"), nullable=False, index=True)
    transaction_date = Column(DateTime, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    transaction_type = Column(String, nullable=False)  # "credit" or "debit"
    reference = Column(String, nullable=True)
    extracted_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    pdf_document = relationship("PDFDocument", back_populates="transactions")
    
    class Config:
        from_attributes = True


class ExtractedText(Base):
    """Model for storing raw extracted text from PDFs."""
    
    __tablename__ = "extracted_text"
    
    id = Column(Integer, primary_key=True, index=True)
    pdf_document_id = Column(Integer, ForeignKey("pdf_documents.id"), unique=True, nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    extraction_method = Column(String, nullable=False)  # "pdf_reader" or "ocr"
    extraction_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    pdf_document = relationship("PDFDocument", back_populates="extracted_text")
    
    class Config:
        from_attributes = True
