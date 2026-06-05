"""M5 - Document Parsing Module Start
Tests document parsing strategy, classification, redaction, and evaluation output.
M5/M6 End"""

import json

import pytest

from app.models.parsing import ParseStatus
from app.services import classification_service
from app.services.classification_service import classify_document
from app.services.parsing_service import _is_tesseract_available, parse_document_content
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
    assert result.classification.document_subtype == "service_invoice"
    assert result.evaluation.document_id == "ing_123"
    assert result.evaluation.predicted_document_subtype == "service_invoice"
    assert result.extraction_handoff.parse_id == result.parse_id
    assert result.extraction_handoff.strategy == "pdf_text"
    assert result.extraction_handoff.extraction_ready is True
    assert result.extraction_handoff.transaction_signal_count > 0


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


def test_real_scanned_pdf_uses_tesseract_ocr_and_classifies_credit_card_statement(input_file):
    pdf_file = input_file("202312_HSBC_4028-9391-1618-2659.pdf")
    result = parse_document_content(
        content=pdf_file.read_bytes(),
        filename=pdf_file.name,
        provided_content_type="application/pdf",
        allow_ocr_fallback=True,
    )

    assert result.status in {ParseStatus.completed, ParseStatus.completed_with_warnings}
    assert result.strategy.selected_strategy == "tesseract_ocr"
    assert result.strategy.ocr_attempted is True
    assert result.metadata.extraction_method == "ocr"
    assert result.classification.document_type == "statement"
    assert result.classification.document_subtype == "credit_card_statement"
    assert result.extraction_handoff.ocr_engine == "tesseract"
    assert result.extraction_handoff.ocr_attempted is True
    assert result.extraction_handoff.tesseract_available is True
    assert result.extraction_handoff.extraction_ready is True
    assert any(page.ocr_word_blocks for page in result.pages)


def test_real_payment_terminal_image_uses_tesseract_ocr(input_file):
    image_file = input_file("20260528_083213.jpg")
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )

    assert result.status == ParseStatus.completed
    assert result.strategy.selected_strategy == "tesseract_ocr"
    assert result.metadata.extraction_method == "ocr"
    assert result.metadata.ocr_quality_score is not None
    assert result.classification.document_type == "receipt"
    assert result.classification.document_subtype == "payment_terminal_receipt"
    assert result.extraction_handoff.strategy == "tesseract_ocr"
    assert result.extraction_handoff.transaction_signal_count > 0
    assert "227.00" in result.text or "227,00" in result.text
    assert any(page.ocr_word_blocks for page in result.pages)


def test_extraction_handoff_redacts_sensitive_preview(monkeypatch, sample_pdf_content):
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

    assert result.extraction_handoff.extraction_ready is True
    assert "[REDACTED_CARD]" in result.extraction_handoff.redacted_preview
    assert "4111 1111 1111 1111" not in result.extraction_handoff.redacted_preview
    assert result.extraction_handoff.redaction_applied is True


def test_text_pdf_parse_classifies_credit_card_statement_subtype(monkeypatch, sample_pdf_content):
    statement_text = (
        "Credit Cards Statement of Account Card Type Gold Mastercard "
        "Credit Limit 989,000.00 Minimum Amount Due 1,612.08 "
        "Payment Due Date November 28, 2023 Previous Balance 77,803.97 "
        "Finance Charge Unbilled Installment Total Outstanding Balance"
    )
    monkeypatch.setattr("app.services.parsing_service._extract_pdf_text", lambda content, page_limit: (statement_text, [], 1))

    result = parse_document_content(
        content=sample_pdf_content,
        filename="statement.pdf",
        provided_content_type="application/pdf",
    )

    assert result.strategy.selected_strategy == "pdf_text"
    assert result.classification.document_type == "statement"
    assert result.classification.document_subtype == "credit_card_statement"
    assert "CREDIT_CARD_STATEMENT_SIGNALS" in result.classification.reason_codes


def test_classifier_keeps_hsbc_statement_ahead_of_generic_receipt_signals():
    result = classify_document(
        text=(
            "HSBC CLASSIC VISA Credit Limit Payment Due Date Finance Charge "
            "GST total card purchase wording appears in the statement footer."
        ),
        supported_document_types=["statement", "receipt", "invoice", "unknown"],
        confidence_threshold=0.35,
        allow_unknown=True,
    )

    assert result.document_type == "statement"
    assert result.document_subtype == "credit_card_statement"
    assert "STATEMENT_AMBIGUITY_RESOLVED" in result.reason_codes


def test_classification_loads_configured_vocabulary_and_rules(monkeypatch, tmp_path):
    vocabulary_path = tmp_path / "vocabulary.json"
    rules_path = tmp_path / "rules.json"
    vocabulary_path.write_text(
        json.dumps(
            {
                "document_types": ["invoice", "unknown"],
                "document_subtypes": {"invoice": ["service_invoice", "unknown"], "unknown": ["unknown"]},
            }
        ),
        encoding="utf-8",
    )
    rules_path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "document_type": "invoice",
                        "document_subtype": "service_invoice",
                        "reason_code": "CUSTOM_SERVICE_INVOICE_RULE",
                        "required_any": ["custom service invoice"],
                        "signals": ["balance payable", "invoice total"],
                        "minimum_score": 0.1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(classification_service.settings, "document_classification_vocabulary_path", vocabulary_path)
    monkeypatch.setattr(classification_service.settings, "document_classification_rules_path", rules_path)
    classification_service._load_vocabulary.cache_clear()
    classification_service._load_rules.cache_clear()

    try:
        result = classify_document(
            text="Custom service invoice with invoice total and balance payable.",
            supported_document_types=["invoice", "unknown"],
            confidence_threshold=0.2,
            allow_unknown=True,
        )
    finally:
        classification_service._load_vocabulary.cache_clear()
        classification_service._load_rules.cache_clear()

    assert result.document_type == "invoice"
    assert result.document_subtype == "service_invoice"
    assert "CUSTOM_SERVICE_INVOICE_RULE" in result.reason_codes


def test_classification_falls_back_when_configured_json_is_missing_or_malformed(monkeypatch, tmp_path):
    missing_vocabulary_path = tmp_path / "missing-vocabulary.json"
    malformed_rules_path = tmp_path / "rules.json"
    malformed_rules_path.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr(classification_service.settings, "document_classification_vocabulary_path", missing_vocabulary_path)
    monkeypatch.setattr(classification_service.settings, "document_classification_rules_path", malformed_rules_path)
    classification_service._load_vocabulary.cache_clear()
    classification_service._load_rules.cache_clear()

    try:
        result = classify_document(
            text=(
                "Credit Cards Statement of Account Card Type Gold Mastercard "
                "Credit Limit 989,000.00 Minimum Amount Due 1,612.08 Payment Due Date"
            ),
            supported_document_types=["statement", "receipt", "invoice", "unknown"],
            confidence_threshold=0.2,
            allow_unknown=True,
        )
    finally:
        classification_service._load_vocabulary.cache_clear()
        classification_service._load_rules.cache_clear()

    assert result.document_type == "statement"
    assert result.document_subtype == "credit_card_statement"
    assert "CREDIT_CARD_STATEMENT_SIGNALS" in result.reason_codes


def test_real_image_ocr_classifies_payment_terminal_receipt_subtype(input_file):
    image_file = input_file("20260528_083213.jpg")
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )

    assert result.status in {ParseStatus.completed, ParseStatus.completed_with_warnings}
    assert result.classification.document_type == "receipt"
    assert result.classification.document_subtype == "payment_terminal_receipt"
    assert "PAYMENT_TERMINAL_RECEIPT_SIGNALS" in result.classification.reason_codes


def test_real_image_ocr_classifies_medical_invoice_subtype(input_file):
    image_file = input_file("20260528_083238.jpg")
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )

    assert result.classification.document_type == "invoice"
    assert result.classification.document_subtype == "medical_invoice"
    assert "MEDICAL_INVOICE_SIGNALS" in result.classification.reason_codes


def test_real_image_ocr_records_orientation_retry_metadata(input_file):
    image_file = input_file("20260528_083256.jpg")
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )
    codes = {finding.code for finding in result.findings}

    assert result.status == ParseStatus.completed
    assert "OCR_ORIENTATION_RETRIED" in codes
    assert result.metadata.ocr_attempt_count and result.metadata.ocr_attempt_count > 1
    assert result.classification.document_type == "receipt"
    assert result.classification.document_subtype == "tax_receipt"


@pytest.mark.parametrize(
    "filename",
    [
        "20260603_103901.jpg",
        "20260603_103956.jpg",
        "20260603_103920.jpg",
        "20260603_104027.jpg",
    ],
)
def test_real_retail_receipt_images_classify_as_receipts(input_file, filename):
    image_file = input_file(filename)
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )

    assert result.status in {ParseStatus.completed, ParseStatus.completed_with_warnings}
    assert result.quality.text_length > 100
    assert result.classification.document_type == "receipt"
    assert result.classification.document_subtype in {"tax_receipt", "payment_terminal_receipt"}


@pytest.mark.parametrize(
    ("filename", "expected_fragments"),
    [
        ("20260603_104027.jpg", ["19/04/26", "15:28", "19.92"]),
        ("20260603_122232.jpg", ["13 Aug 25", "13:16", "55.00"]),
    ],
)
def test_real_receipt_photo_ocr_preserves_terminal_date_and_amount(input_file, filename, expected_fragments):
    image_file = input_file(filename)
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
        allow_ocr_fallback=True,
    )

    normalized_text = " ".join(result.text.split())

    assert result.status in {ParseStatus.completed, ParseStatus.completed_with_warnings}
    assert result.classification.document_type == "receipt"
    for fragment in expected_fragments:
        assert fragment in normalized_text


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


def test_image_with_ocr_disabled_fails_explicitly(input_file):
    image_file = input_file("20260528_083213.jpg")
    result = parse_document_content(
        content=image_file.read_bytes(),
        filename=image_file.name,
        provided_content_type="image/jpeg",
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
        supported_document_types=["statement", "receipt", "invoice", "payment_proof", "utility_bill", "unknown"],
        confidence_threshold=0.7,
        allow_unknown=True,
    )

    assert result.document_type == "unknown"
    assert result.document_subtype == "unknown"
    assert result.status == "unknown"
    assert "POSSIBLE_NEW_DOCUMENT_SHAPE" in result.reason_codes or "NO_CLASSIFICATION_SIGNALS" in result.reason_codes
