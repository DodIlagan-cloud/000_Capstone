"""M7 - Transaction Extraction Module Start
Verifies transaction and financial field candidate extraction behavior.
M7 End"""

from app.models.extraction import TransactionExtractionRequest
from app.services.extraction_service import extract_transactions


def test_missing_text_fails_with_explicit_finding():
    result = extract_transactions(TransactionExtractionRequest(text="", document_type="bank_statement"))

    assert result.status == "failed"
    assert result.summary.transaction_candidate_count == 0
    assert result.evaluation.finding_counts["MISSING_TEXT"] == 1


def test_bank_statement_extracts_transaction_and_financial_candidates(bank_statement_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_test",
            document_type="bank_statement",
            text=bank_statement_text,
        )
    )

    assert result.status == "completed"
    assert result.parse_id == "parse_test"
    assert result.summary.transaction_candidate_count == 2
    assert result.summary.financial_field_candidate_count >= 4
    assert result.summary.amount_total == 80149.64
    assert {candidate.direction for candidate in result.transaction_candidates} >= {"credit", "debit"}
    assert "total_amount_due" in {field.field_name for field in result.financial_field_candidates}
    assert result.evaluation.transaction_candidate_count == 2


def test_proof_of_payment_extracts_transfer_amount_and_confirmation(proof_of_payment_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text=proof_of_payment_text,
        )
    )

    field_names = {field.field_name for field in result.financial_field_candidates}

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].amount == 17274.97
    assert "transfer_amount" in field_names
    assert "confirmation_number" in field_names


def test_unknown_document_type_lowers_confidence_but_returns_candidates():
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="unknown",
            text="2026-01-08 Transfer to ACQUA EDEN RE PHP 17,274.97",
            options={"min_confidence": 0.85},
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 1
    assert result.summary.low_confidence_candidate_count == 1
    assert result.evaluation.finding_counts["NO_FINANCIAL_FIELDS"] == 1
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_EXTRACTION"] == 1


def test_m5_shaped_payload_uses_classification_and_quality_context(proof_of_payment_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_from_m5",
            classification={
                "document_type": "receipt",
                "confidence": 0.82,
                "status": "classified",
            },
            text=proof_of_payment_text,
            pages=[{"page_number": 1, "text": proof_of_payment_text}],
            quality={
                "text_length": len(proof_of_payment_text),
                "page_count": 1,
                "pages_processed": 1,
                "empty_page_count": 0,
                "low_text": False,
            },
            findings=[],
        )
    )

    assert result.status == "completed"
    assert result.document_type == "receipt"
    assert result.evaluation.parse_id == "parse_from_m5"
    assert result.summary.pages_processed == 1
    assert result.summary.transaction_candidate_count == 1


def test_m5_low_text_and_ocr_findings_are_carried_as_input_quality_warnings():
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_low_quality",
            classification={"document_type": "unknown", "confidence": 0.2},
            text="blurred text",
            quality={
                "text_length": 12,
                "page_count": 1,
                "pages_processed": 1,
                "empty_page_count": 0,
                "low_text": True,
            },
            findings=[
                {
                    "code": "OCR_FALLBACK_DISABLED",
                    "severity": "warning",
                    "message": "Image input requires OCR and OCR fallback is disabled.",
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.evaluation.finding_counts["LOW_TEXT_QUALITY_INPUT"] == 1
    assert result.evaluation.finding_counts["UPSTREAM_OCR_DISABLED"] == 1
    assert result.evaluation.finding_counts["NO_TRANSACTION_CANDIDATES"] == 1


def test_m5_weak_ocr_quality_is_carried_as_input_quality_warning():
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_noisy_ocr",
            classification={"document_type": "unknown", "confidence": 0.0},
            text="||| OOO ___ 123",
            findings=[
                {
                    "code": "LOW_OCR_CONFIDENCE",
                    "severity": "warning",
                    "message": "Tesseract OCR confidence was below the configured threshold.",
                },
                {
                    "code": "OCR_TEXT_NOISY",
                    "severity": "warning",
                    "message": "OCR produced noisy text.",
                },
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.evaluation.finding_counts["UPSTREAM_OCR_QUALITY_WEAK"] == 1
    assert result.evaluation.finding_counts["NO_TRANSACTION_CANDIDATES"] == 1


def test_single_line_invoice_ocr_extracts_invoice_and_gst_fields(single_line_invoice_ocr_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="invoice",
            text=single_line_invoice_ocr_text,
        )
    )

    field_values = {field.field_name: field.normalized_value for field in result.financial_field_candidates}

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert field_values["invoice_number"] == "384590"
    assert field_values["total_gst"] == "29.61"


def test_single_line_pharmacy_receipt_ocr_extracts_total_gst_and_purchase(single_line_pharmacy_receipt_ocr_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text=single_line_pharmacy_receipt_ocr_text,
        )
    )

    fields = {field.field_name: field for field in result.financial_field_candidates}

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert fields["receipt_total"].normalized_value == "94.25"
    assert fields["gst_amount"].normalized_value == "12.29"
    assert fields["purchase_amount"].normalized_value == "94.25"


def test_single_line_card_receipt_ocr_extracts_card_amount(single_line_card_receipt_ocr_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text=single_line_card_receipt_ocr_text,
        )
    )

    fields = {field.field_name: field for field in result.financial_field_candidates}

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert fields["card_receipt_amount"].normalized_value == "227.00"
    assert fields["card_receipt_amount"].currency == "NZD"


def test_text_without_financial_values_returns_no_candidate_findings():
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="invoice",
            text="This document contains notes but no amounts or dates.",
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 0
    assert result.summary.financial_field_candidate_count == 0
    assert result.evaluation.finding_counts["NO_TRANSACTION_CANDIDATES"] == 1
    assert result.evaluation.finding_counts["NO_FINANCIAL_FIELDS"] == 1
