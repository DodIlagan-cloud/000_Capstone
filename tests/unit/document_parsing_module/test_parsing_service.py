"""M5 - Document Parsing Module Start
Tests document parsing strategy, classification, redaction, and evaluation output.
M5/M6 End"""

from app.models.parsing import ParseStatus
from app.services.classification_service import classify_document
from app.services.parsing_service import parse_document_content
from app.services.redaction_service import redact_text


def test_text_pdf_parse_classifies_invoice_and_exposes_evaluation(monkeypatch, sample_pdf_content):
    invoice_text = "Invoice Number 123 Amount Due 54.10 Due Date 2026-06-01 Bill To Household"
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: (invoice_text, [], 1))

    result = parse_document_content(
        content=sample_pdf_content,
        filename="invoice.pdf",
        provided_content_type="application/pdf",
        ingestion_id="ing_123",
        classification_threshold=0.2,
    )

    assert result.status == ParseStatus.completed
    assert result.strategy.selected_strategy == "pdf_text"
    assert result.metadata.extraction_method == "direct_pdf_text"
    assert result.classification.document_type == "invoice"
    assert result.evaluation.document_id == "ing_123"


def test_pdf_with_no_text_reports_ocr_disabled(monkeypatch, sample_pdf_content):
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: ("", [], 1))

    result = parse_document_content(
        content=sample_pdf_content,
        filename="scan.pdf",
        provided_content_type="application/pdf",
        allow_ocr_fallback=False,
    )
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.completed_with_warnings
    assert "OCR_FALLBACK_DISABLED" in codes
    assert "CLASSIFICATION_UNKNOWN" in codes


def test_pdf_with_no_text_uses_tesseract_ocr_when_available(monkeypatch, sample_pdf_content):
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: ("", [], 1))
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: True)
    monkeypatch.setattr("app.services.parsing_service._is_pdf_renderer_available", lambda: True)
    monkeypatch.setattr("app.services.parsing_service._ocr_pdf_pages", lambda content, page_limit, language: ("Receipt Total GST EFTPOS Merchant", [], 1))

    result = parse_document_content(
        content=sample_pdf_content,
        filename="scan.pdf",
        provided_content_type="application/pdf",
        allow_ocr_fallback=True,
        classification_threshold=0.2,
    )

    assert result.status == ParseStatus.completed
    assert result.strategy.selected_strategy == "tesseract_ocr"
    assert result.strategy.ocr_attempted is True
    assert result.metadata.extraction_method == "ocr"
    assert result.classification.document_type == "receipt"


def test_image_with_ocr_enabled_uses_tesseract_when_available(monkeypatch):
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: True)
    monkeypatch.setattr("app.services.parsing_service._ocr_image_content", lambda content, language: ("Utility Bill Usage Charges Due Date", [], 1))

    result = parse_document_content(
        content=b"\x89PNG\r\n\x1a\nfake",
        filename="bill.png",
        provided_content_type="image/png",
        allow_ocr_fallback=True,
        classification_threshold=0.2,
    )

    assert result.status == ParseStatus.completed
    assert result.strategy.selected_strategy == "tesseract_ocr"
    assert result.metadata.extraction_method == "ocr"
    assert result.classification.document_type == "utility_bill"


def test_pdf_ocr_reports_renderer_unavailable(monkeypatch, sample_pdf_content):
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: ("", [], 1))
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: True)
    monkeypatch.setattr("app.services.parsing_service._is_pdf_renderer_available", lambda: False)

    result = parse_document_content(
        content=sample_pdf_content,
        filename="scan.pdf",
        provided_content_type="application/pdf",
        allow_ocr_fallback=True,
    )
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.failed
    assert "PDF_RENDERER_UNAVAILABLE" in codes


def test_pdf_ocr_reports_tesseract_unavailable(monkeypatch, sample_pdf_content):
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: ("", [], 1))
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: False)

    result = parse_document_content(
        content=sample_pdf_content,
        filename="scan.pdf",
        provided_content_type="application/pdf",
        allow_ocr_fallback=True,
    )
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.failed
    assert result.strategy.selected_strategy == "tesseract_ocr"
    assert "TESSERACT_UNAVAILABLE" in codes


def test_image_with_ocr_disabled_fails_explicitly():
    result = parse_document_content(
        content=b"\x89PNG\r\n\x1a\nfake",
        filename="receipt.png",
        provided_content_type="image/png",
        allow_ocr_fallback=False,
    )
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.failed
    assert result.strategy.selected_strategy == "ocr_disabled"
    assert "OCR_FALLBACK_DISABLED" in codes


def test_unsupported_media_type_returns_unsupported():
    result = parse_document_content(content=b"plain text", filename="notes.txt", provided_content_type="text/plain")
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.unsupported
    assert "UNSUPPORTED_MEDIA_TYPE" in codes


def test_redaction_masks_sensitive_evidence_values():
    redacted, counts = redact_text(
        "Customer Name: Jane Citizen email jane@example.com card 4111 1111 1111 1111 Account Number: ABC12345",
        preview_chars=300,
    )

    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_CARD]" in redacted
    assert "[REDACTED_ACCOUNT]" in redacted
    assert counts["REDACTED_EMAIL"] == 1
    assert counts["REDACTED_CARD"] == 1


def test_classifier_returns_unknown_when_confidence_is_low():
    result = classify_document(
        text="financial document with very few useful signals",
        supported_document_types=["bank_statement", "receipt", "invoice", "utility_bill", "unknown"],
        confidence_threshold=0.7,
        allow_unknown=True,
    )

    assert result.document_type == "unknown"
    assert result.status == "unknown"
