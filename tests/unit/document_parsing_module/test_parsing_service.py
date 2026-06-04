"""M5 - Document Parsing Module Start
Tests document parsing strategy, classification, redaction, and evaluation output.
M5/M6 End"""

from app.models.parsing import ParseStatus
from app.services.classification_service import classify_document
from app.services.parsing_service import _is_tesseract_available, _ocr_best_image, parse_document_content
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
    assert result.m7_handoff.parse_id == result.parse_id
    assert result.m7_handoff.strategy == "pdf_text"
    assert result.m7_handoff.m7_ready is True
    assert result.m7_handoff.transaction_signal_count > 0


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
    monkeypatch.setattr(
        "app.services.parsing_service._ocr_pdf_pages",
        lambda content, page_limit, language: (
            "Receipt Total GST EFTPOS Merchant",
            [],
            1,
            {
                "quality_score": 0.9,
                "mean_confidence": 86.0,
                "selected_orientation": 0,
                "selected_psm": 6,
                "attempt_count": 1,
                "alnum_ratio": 0.9,
                "keyword_hits": 3,
            },
        ),
    )

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
    assert result.m7_handoff.ocr_engine == "tesseract"
    assert result.m7_handoff.ocr_attempted is True
    assert result.m7_handoff.tesseract_available is True
    assert result.m7_handoff.m7_ready is True


def test_image_with_ocr_enabled_uses_tesseract_when_available(monkeypatch):
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: True)
    monkeypatch.setattr(
        "app.services.parsing_service._ocr_image_content",
        lambda content, language: (
            "Utility Bill Usage Charges Due Date",
            [],
            1,
            {
                "quality_score": 0.9,
                "mean_confidence": 88.0,
                "selected_orientation": 0,
                "selected_psm": 6,
                "attempt_count": 1,
                "alnum_ratio": 0.9,
                "keyword_hits": 4,
            },
        ),
    )

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
    assert result.metadata.ocr_quality_score == 0.9
    assert result.metadata.ocr_selected_orientation == 0
    assert result.classification.document_type == "utility_bill"
    assert result.m7_handoff.strategy == "tesseract_ocr"
    assert result.m7_handoff.transaction_signal_count > 0


def test_m7_handoff_redacts_sensitive_preview(monkeypatch, sample_pdf_content):
    text = (
        "Bank Statement account number ABC12345 card 4111 1111 1111 1111 "
        "payment 2026-05-28 amount 42.00"
    )
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: (text, [], 1))

    result = parse_document_content(
        content=sample_pdf_content,
        filename="statement.pdf",
        provided_content_type="application/pdf",
        classification_threshold=0.2,
    )

    assert result.m7_handoff.m7_ready is True
    assert "[REDACTED_CARD]" in result.m7_handoff.redacted_preview
    assert "4111 1111 1111 1111" not in result.m7_handoff.redacted_preview
    assert result.m7_handoff.redaction_applied is True


def test_image_ocr_retries_orientation_and_selects_best_attempt(monkeypatch):
    from PIL import Image

    def fake_ocr(image, language, psm):
        if image.height > image.width:
            return "Payment Amount 12.00 Transfer Date 2026-05-28", 82.0
        return "OOO lll |||", 18.0

    monkeypatch.setattr("app.services.parsing_service._ocr_image_with_confidence", fake_ocr)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_retry_orientations", True)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_psm_values", [6])

    attempt = _ocr_best_image(Image.new("RGB", (1600, 900), "white"), "eng")

    assert attempt.orientation in {90, 270}
    assert "Payment Amount" in attempt.text
    assert attempt.quality_score > 0.35
    assert attempt.attempt_count == 8


def test_noisy_ocr_output_returns_quality_findings(monkeypatch):
    monkeypatch.setattr("app.services.parsing_service._is_tesseract_available", lambda: True)
    monkeypatch.setattr(
        "app.services.parsing_service._ocr_image_content",
        lambda content, language: (
            "||| OOO ___",
            [],
            1,
            {
                "quality_score": 0.1,
                "mean_confidence": 12.0,
                "selected_orientation": 90,
                "selected_psm": 11,
                "attempt_count": 8,
                "alnum_ratio": 0.2,
                "keyword_hits": 0,
            },
        ),
    )

    result = parse_document_content(
        content=b"\x89PNG\r\n\x1a\nfake",
        filename="noisy.png",
        provided_content_type="image/png",
        allow_ocr_fallback=True,
    )
    codes = {finding.code for finding in result.findings}

    assert "LOW_OCR_CONFIDENCE" in codes
    assert "OCR_TEXT_NOISY" in codes
    assert result.metadata.ocr_selected_orientation == 90


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


def test_invalid_tesseract_version_is_reported_unavailable(monkeypatch):
    class FakeTesseract:
        class pytesseract:
            tesseract_cmd = ""

        @staticmethod
        def get_tesseract_version():
            raise SystemExit("Invalid tesseract version")

    monkeypatch.setattr("app.services.parsing_service.settings.ocr_engine", "tesseract")
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", FakeTesseract)

    assert _is_tesseract_available() is False


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


def test_classifier_detects_bank_statement_from_expanded_signals():
    result = classify_document(
        text=(
            "Bank Statement Account Number 12345 Statement Date 2026-05-31 "
            "Opening Balance 100.00 Closing Balance 75.00 Transaction History Debit Credit"
        ),
        supported_document_types=["bank_statement", "receipt", "invoice", "utility_bill", "unknown"],
        confidence_threshold=0.3,
        allow_unknown=True,
    )

    assert result.document_type == "bank_statement"
    assert result.status == "classified"
    assert result.scores["bank_statement"] >= 0.3
    assert "BANK_STATEMENT_SIGNALS" in result.reason_codes


def test_classifier_detects_receipt_from_payment_terminal_signals():
    result = classify_document(
        text="Receipt Merchant Terminal EFTPOS Purchase Approved GST Subtotal Total Card",
        supported_document_types=["bank_statement", "receipt", "invoice", "utility_bill", "unknown"],
        confidence_threshold=0.3,
        allow_unknown=True,
    )

    assert result.document_type == "receipt"
    assert result.status == "classified"
    assert result.scores["receipt"] >= 0.3
    assert "RECEIPT_SIGNALS" in result.reason_codes


def test_classifier_reports_ambiguous_when_top_scores_are_close():
    result = classify_document(
        text="Invoice Amount Due Due Date Receipt Total GST",
        supported_document_types=["receipt", "invoice", "unknown"],
        confidence_threshold=0.2,
        allow_unknown=True,
    )

    assert result.document_type == "unknown"
    assert result.status == "ambiguous"
    assert "AMBIGUOUS_DOCUMENT_SIGNALS" in result.reason_codes
