"""M5 - Document Parsing Module Start
Tests document parsing strategy, classification, redaction, and evaluation output.
M5/M6 End"""

import json
from pathlib import Path

import pytest
from PIL import Image

from app.models.parsing import ParseStatus
from app.models.parsing import ClassificationResult
from app.services import ai_classification_service
from app.services import classification_service
from app.services.classification_service import classify_document
from app.services.parsing_service import (
    _document_crop_variant,
    _is_tesseract_available,
    _ocr_best_image,
    _receipt_amount_coherence,
    parse_document_content,
)
from app.services.redaction_service import redact_text


def _active_recognition_settings_payload() -> dict:
    config_dir = Path(__file__).resolve().parents[3] / "config"
    return {
        "document_vocabulary": json.loads((config_dir / "document-classification.vocabulary.json").read_text(encoding="utf-8")),
        "document_rules": json.loads((config_dir / "document-classification.rules.json").read_text(encoding="utf-8")),
    }


@pytest.fixture(autouse=True)
def m9_active_recognition_settings(monkeypatch):
    classification_service._clear_settings_cache()
    monkeypatch.setattr(classification_service, "_load_active_settings", lambda: _active_recognition_settings_payload())
    yield
    classification_service._clear_settings_cache()


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


def test_pdf_ocr_fast_profile_stops_when_quality_is_sufficient(monkeypatch):
    calls = []

    def fake_ocr(image, language, psm, page_number):
        calls.append(psm)
        return (
            "Statement transaction date amount total payment 2026-01-01 PHP 123.45",
            82.0,
            [],
        )

    monkeypatch.setattr("app.services.parsing_service._ocr_image_with_confidence", fake_ocr)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_pdf_fast_psm_values", [6])
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_fast_min_quality_score", 0.35)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_fast_min_text_length", 20)

    attempt = _ocr_best_image(Image.new("RGB", (240, 240), "white"), "eng", fast_pdf_profile=True)

    assert attempt.attempt_count == 2
    assert attempt.psm == 6
    assert calls == [6, 6]


def test_image_ocr_stops_early_when_receipt_evidence_is_strong(monkeypatch):
    calls = []

    def fake_ocr(image, language, psm, page_number):
        calls.append(psm)
        return (
            "Tax Invoice receipt DATE: 08-06-2026 12:19 TOTAL: $34.33 EFTPOS: $34.33 INCLUDE TAX: $4.48",
            78.0,
            [],
        )

    monkeypatch.setattr("app.services.parsing_service._ocr_image_with_confidence", fake_ocr)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_image_fast_psm_values", [6, 11])
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_image_fast_min_quality_score", 0.35)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_image_fast_min_text_length", 20)
    monkeypatch.setattr("app.services.parsing_service.settings.ocr_image_fast_min_confidence", 50.0)

    attempt = _ocr_best_image(Image.new("RGB", (240, 240), "white"), "eng")

    assert attempt.attempt_count == 1
    assert attempt.early_stopped is True
    assert attempt.early_stop_reason == "STRONG_RECEIPT_AND_CLEAN_TOTAL"
    assert attempt.amount_coherence_status == "clean"
    assert calls == [6]


def test_document_crop_variant_trims_bright_receipt_region():
    image = Image.new("RGB", (1000, 1000), "#303030")
    receipt = Image.new("RGB", (420, 760), "white")
    image.paste(receipt, (260, 90))

    cropped = _document_crop_variant(image)

    assert cropped is not None
    assert cropped.width < image.width
    assert cropped.height < image.height
    assert cropped.width > 350
    assert cropped.height > 650


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


def test_classification_loads_m9_active_vocabulary_and_rules(monkeypatch):
    monkeypatch.setattr(
        classification_service,
        "_load_active_settings",
        lambda: {
            "document_vocabulary": {
                "document_types": ["invoice", "unknown"],
                "document_subtypes": {"invoice": ["service_invoice", "unknown"], "unknown": ["unknown"]},
            },
            "document_rules": {
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
            },
        },
    )

    result = classify_document(
        text="Custom service invoice with invoice total and balance payable.",
        supported_document_types=["invoice", "unknown"],
        confidence_threshold=0.2,
        allow_unknown=True,
    )

    assert result.document_type == "invoice"
    assert result.document_subtype == "service_invoice"
    assert "CUSTOM_SERVICE_INVOICE_RULE" in result.reason_codes


def test_m9_slug_signals_match_statement_phrase_text(monkeypatch):
    monkeypatch.setattr(
        classification_service,
        "_load_active_settings",
        lambda: {
            "document_vocabulary": {
                "document_types": ["statement", "receipt", "unknown"],
                "document_subtypes": {
                    "statement": ["credit_card_statement", "unknown"],
                    "receipt": ["tax_receipt", "unknown"],
                    "unknown": ["unknown"],
                },
            },
            "document_rules": {
                "rules": [
                    {
                        "document_type": "statement",
                        "document_subtype": "credit_card_statement",
                        "reason_code": "CREDIT_CARD_STATEMENT_SIGNALS",
                        "required_any": ["statement_of_account"],
                        "signals": [
                            "credit_limit",
                            "minimum_amount_due",
                            "payment_due_date",
                            "previous_balance",
                        ],
                        "minimum_score": 0.1,
                    },
                    {
                        "document_type": "receipt",
                        "document_subtype": "tax_receipt",
                        "reason_code": "GENERIC_RECEIPT_SIGNALS",
                        "required_any": ["card"],
                        "signals": ["total", "purchase", "payment", "card"],
                        "minimum_score": 0.1,
                    },
                ]
            },
        },
    )

    result = classify_document(
        text=(
            "Credit Cards Statement of Account Credit Limit 989,000.00 "
            "Minimum Amount Due 1,612.08 Payment Due Date November 28, 2023 "
            "Previous Balance 77,803.97 total purchase payment card"
        ),
        supported_document_types=["statement", "receipt", "unknown"],
        confidence_threshold=0.35,
        allow_unknown=True,
    )

    assert result.document_type == "statement"
    assert result.document_subtype == "credit_card_statement"
    assert "CREDIT_CARD_STATEMENT_SIGNALS" in result.reason_codes


def test_classification_requires_m9_active_settings(monkeypatch):
    monkeypatch.setattr(classification_service, "_load_active_settings", lambda: None)

    result = classify_document(
        text=(
            "Credit Cards Statement of Account Card Type Gold Mastercard "
            "Credit Limit 989,000.00 Minimum Amount Due 1,612.08 Payment Due Date"
        ),
        supported_document_types=["statement", "receipt", "invoice", "unknown"],
        confidence_threshold=0.2,
        allow_unknown=True,
    )

    assert result.document_type == "unknown"
    assert result.document_subtype == "unknown"
    assert result.status == "unknown"
    assert result.requires_review is True
    assert "RECOGNITION_SETTINGS_UNAVAILABLE" in result.reason_codes


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


def test_receipt_amount_coherence_accepts_clean_final_total():
    result = _receipt_amount_coherence(
        "Tax Invoice DATE 08-06-2026 TOTAL: $34.33 EFTPOS: $34.33 INCLUDE TAX: $4.48"
    )

    assert result["status"] == "clean"
    assert result["score"] >= 3
    assert "CLEAN_LABELLED_AMOUNT" in result["reasons"]


def test_receipt_amount_coherence_rejects_damaged_competing_totals():
    result = _receipt_amount_coherence(
        "HOP Puhinui COMPLETE NZD55 . OF TOTAL NZ055 00 "
        "Unregistered HOP money Sale 3 $5.00 Due amount $ 56.00"
    )

    assert result["status"] == "conflicting"
    assert "DAMAGED_LABELLED_AMOUNT" in result["reasons"]


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


def test_classifier_keeps_ai_fallback_disabled_by_default(monkeypatch):
    calls = []

    def fake_ai_classify(**_kwargs):
        calls.append("called")
        return ClassificationResult(
            document_type="receipt",
            document_subtype="tax_receipt",
            confidence=0.91,
            status="classified",
            reason_codes=["AI_RECEIPT_SIGNALS"],
            scores={"ai.receipt.tax_receipt": 0.91},
            classification_source="ai_assist",
            ai_model_name="test-model",
            ai_model_version="test-v1",
            ai_confidence=0.91,
        )

    monkeypatch.setattr(classification_service.settings, "classification_ai_enabled", False)
    monkeypatch.setattr(classification_service, "ai_classify_document", fake_ai_classify)

    result = classify_document(
        text="financial document with very few useful signals",
        supported_document_types=["statement", "receipt", "invoice", "payment_proof", "utility_bill", "unknown"],
        confidence_threshold=0.7,
        allow_unknown=True,
    )

    assert calls == []
    assert result.document_type == "unknown"
    assert result.classification_source == "rules"


def test_classifier_uses_ai_fallback_for_unknown_document_shape(monkeypatch):
    def fake_ai_classify(**_kwargs):
        return ClassificationResult(
            document_type="receipt",
            document_subtype="tax_receipt",
            confidence=0.88,
            status="classified",
            reason_codes=["AI_RECEIPT_SIGNALS"],
            scores={"ai.receipt.tax_receipt": 0.88},
            classification_source="ai_assist",
            ai_model_name="test-model",
            ai_model_version="test-v1",
            ai_confidence=0.88,
        )

    monkeypatch.setattr(classification_service.settings, "classification_ai_enabled", True)
    monkeypatch.setattr(classification_service.settings, "classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(classification_service.settings, "classification_ai_trigger_threshold", 0.70)
    monkeypatch.setattr(classification_service, "ai_classify_document", fake_ai_classify)

    result = classify_document(
        text="faint shop docket total paid with incomplete OCR text",
        supported_document_types=["statement", "receipt", "invoice", "payment_proof", "utility_bill", "unknown"],
        confidence_threshold=0.7,
        allow_unknown=True,
    )

    assert result.document_type == "receipt"
    assert result.document_subtype == "tax_receipt"
    assert result.classification_source == "ai_assist"
    assert result.ai_model_name == "test-model"
    assert result.ai_model_version == "test-v1"
    assert result.ai_confidence == 0.88
    assert "AI_ASSISTED_CLASSIFICATION" in result.reason_codes


def test_classifier_preserves_rule_result_when_ai_conflicts(monkeypatch):
    def fake_ai_classify(**_kwargs):
        return ClassificationResult(
            document_type="receipt",
            document_subtype="tax_receipt",
            confidence=0.92,
            status="classified",
            reason_codes=["AI_RECEIPT_SIGNALS"],
            scores={"ai.receipt.tax_receipt": 0.92},
            classification_source="ai_assist",
            ai_model_name="test-model",
            ai_model_version="test-v1",
            ai_confidence=0.92,
        )

    monkeypatch.setattr(classification_service.settings, "classification_ai_enabled", True)
    monkeypatch.setattr(classification_service.settings, "classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(classification_service.settings, "classification_ai_trigger_threshold", 1.01)
    monkeypatch.setattr(classification_service, "ai_classify_document", fake_ai_classify)

    result = classify_document(
        text="Tax invoice no invoice NHI DOB lab tests price incl service fee payment history paid owing gst gender phone",
        supported_document_types=["statement", "receipt", "invoice", "payment_proof", "utility_bill", "unknown"],
        confidence_threshold=0.2,
        allow_unknown=True,
    )

    assert result.document_type == "invoice"
    assert result.document_subtype == "medical_invoice"
    assert result.classification_source == "rules_ai_conflict"
    assert result.ai_model_name == "test-model"
    assert result.ai_confidence == 0.92
    assert result.requires_review is True
    assert "RULE_AI_CLASSIFICATION_CONFLICT" in result.review_reason_codes


def test_gemini_ai_provider_uses_redacted_text_and_supported_vocabulary(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            return False

        @staticmethod
        def read():
            return json.dumps(
                {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "text": json.dumps(
                                            {
                                                "document_type": "receipt",
                                                "document_subtype": "tax_receipt",
                                                "confidence": 0.89,
                                                "reason_codes": ["GEMINI_RECEIPT_SIGNALS"],
                                                "requires_review": False,
                                            }
                                        )
                                    }
                                ]
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_enabled", True)
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_provider", "gemini")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_endpoint", "")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_api_key_env", "GEMINI_API_KEY")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_model_version", "gemini-2.5-flash")
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_max_chars", 3000)
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(ai_classification_service.urllib.request, "urlopen", fake_urlopen)

    result = ai_classification_service.ai_classify_document(
        text="Tax invoice total $34.33 card 4111 1111 1111 1111 Account Number: ABC12345",
        supported_document_types=["statement", "receipt", "invoice", "unknown"],
        rule_result=ClassificationResult(
            document_type="unknown",
            document_subtype="unknown",
            confidence=0.1,
            status="unknown",
            reason_codes=["POSSIBLE_NEW_DOCUMENT_SHAPE"],
            scores={},
        ),
    )

    request_text = captured["payload"]["contents"][0]["parts"][0]["text"]

    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    assert captured["headers"]["X-goog-api-key"] == "test-key"
    assert captured["payload"]["generationConfig"]["responseMimeType"] == "application/json"
    assert "4111 1111 1111 1111" not in request_text
    assert "ABC12345" not in request_text
    assert "[REDACTED_CARD]" in request_text
    assert "[REDACTED_ACCOUNT]" in request_text
    assert result is not None
    assert result.document_type == "receipt"
    assert result.document_subtype == "tax_receipt"
    assert result.ai_model_name == "gemini-2.5-flash"


def test_ai_document_label_outside_active_vocabulary_becomes_pending_suggestion():
    rule_result = ClassificationResult(
        document_type="unknown",
        document_subtype="unknown",
        confidence=0.2,
        status="unknown",
        reason_codes=["POSSIBLE_NEW_DOCUMENT_SHAPE"],
        scores={},
    )
    ai_result = ClassificationResult(
        document_type="receipt",
        document_subtype="tax_receipt",
        confidence=0.91,
        status="classified",
        reason_codes=["GEMINI_RECEIPT_SIGNALS"],
        scores={"ai.receipt.tax_receipt": 0.91},
        classification_source="ai_assist",
        ai_model_name="gemini-2.5-flash",
        ai_model_version="gemini-2.5-flash",
        ai_confidence=0.91,
    )

    result = ai_classification_service.merge_rule_and_ai_classification(
        rule_result=rule_result,
        ai_result=ai_result,
        approved_document_types={"statement", "invoice", "unknown"},
    )

    assert result.document_type == "unknown"
    assert result.suggested_document_type == "receipt"
    assert result.suggested_document_subtype == "tax_receipt"
    assert result.recognition_suggestion_status == "pending"
    assert result.requires_review is True
    assert "PENDING_DOCUMENT_LABEL_SUGGESTION" in result.review_reason_codes
