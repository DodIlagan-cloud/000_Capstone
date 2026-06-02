"""M7 - Transaction Extraction Module Start
Verifies transaction and financial field candidate extraction behavior.
M7 End"""

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "transaction-extraction-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
module_root_path = str(MODULE_ROOT)
if module_root_path in sys.path:
    sys.path.remove(module_root_path)
sys.path.insert(0, module_root_path)

from app.models.extraction import TransactionExtractionRequest
from app.services.extraction_service import extract_transactions


def _word_blocks_from_rows(rows):
    blocks = []
    for row_index, row in enumerate(rows, start=1):
        x = 10
        for token in row.split():
            blocks.append(
                {
                    "page_number": 1,
                    "text": token,
                    "confidence": 90.0,
                    "x": x,
                    "y": row_index * 18,
                    "width": max(8, len(token) * 7),
                    "height": 12,
                }
            )
            x += max(8, len(token) * 7) + 8
    return blocks


def test_missing_text_fails_with_explicit_finding():
    result = extract_transactions(TransactionExtractionRequest(text="", document_type="statement"))

    assert result.status == "failed"
    assert result.summary.transaction_candidate_count == 0
    assert result.evaluation.finding_counts["MISSING_TEXT"] == 1


def test_generic_statement_table_extracts_transaction_and_financial_candidates(generic_statement_table_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_test",
            document_type="statement",
            text=generic_statement_table_text,
        )
    )

    assert result.status == "completed"
    assert result.parse_id == "parse_test"
    assert result.summary.transaction_candidate_count == 2
    assert result.summary.financial_field_candidate_count >= 4
    assert result.summary.section_candidate_count >= 1
    assert result.summary.amount_total == 80149.64
    assert {candidate.direction for candidate in result.transaction_candidates} >= {"credit", "debit"}
    assert "total_amount_due" in {field.field_name for field in result.financial_field_candidates}
    assert {section.section_label for section in result.section_candidates} >= {"statement_summary", "transaction_table"}
    assert result.financial_field_candidates[0].source.source_text_redacted
    assert result.evaluation.transaction_candidate_count == 2


def test_generic_split_statement_table_rows_are_reconstructed(generic_split_statement_table_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_split_table",
            document_type="unknown",
            text=generic_split_statement_table_text,
        )
    )

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 3
    assert [candidate.date_text for candidate in result.transaction_candidates] == [
        "October 12 2023",
        "November 7 2023",
        "November 7 2023",
    ]
    assert result.transaction_candidates[0].posted_date_text == "October 12 2023"
    assert result.transaction_candidates[0].description == "Payment - Thank You"
    assert result.transaction_candidates[0].amount == 77803.97
    assert result.transaction_candidates[0].direction == "credit"
    assert result.transaction_candidates[1].description == "Keds - Sm Megamall MA: 02/03"
    assert result.transaction_candidates[2].description == "Credit-To-Cash 2-Reg: 34/36"
    assert {candidate.source.section_label for candidate in result.transaction_candidates} == {"transaction_table"}
    assert all("STATEMENT_YEAR_INFERRED" in candidate.reason_codes for candidate in result.transaction_candidates)


def test_generic_combined_statement_table_rows_are_reconstructed(generic_combined_statement_table_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_combined_table",
            document_type="unknown",
            text=generic_combined_statement_table_text,
        )
    )

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 3
    assert [candidate.date_text for candidate in result.transaction_candidates] == [
        "October 12 2023",
        "November 7 2023",
        "November 7 2023",
    ]
    assert [candidate.posted_date_text for candidate in result.transaction_candidates] == [
        "October 12 2023",
        "November 7 2023",
        "November 7 2023",
    ]
    assert "Credit Limit" not in {candidate.description for candidate in result.transaction_candidates}
    assert result.transaction_candidates[0].direction == "credit"
    assert result.transaction_candidates[1].direction == "debit"
    assert result.transaction_candidates[1].description == "Credit-To-Cash 2-Reg: 34/36"
    assert result.transaction_candidates[2].amount == 12559.94


def test_flattened_credit_card_statement_ocr_rows_are_reconstructed(flattened_credit_card_statement_ocr_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_flattened_statement",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=flattened_credit_card_statement_ocr_text,
            pages=[{"page_number": 1, "text": flattened_credit_card_statement_ocr_text}],
        )
    )

    assert result.status == "completed"
    assert result.document_type == "statement"
    assert result.summary.transaction_candidate_count >= 3
    assert {candidate.source.section_label for candidate in result.transaction_candidates} == {"transaction_table"}
    assert all("OCR_FLATTENED_ROW_RECONSTRUCTED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert any(candidate.direction == "credit" for candidate in result.transaction_candidates)


def test_layout_word_blocks_extract_tables_and_reconcile_statement():
    rows = [
        "Statement From 13 NOV 2023 to 12 DEC 2023",
        "Previous Statement Balance 1,000.00",
        "Purchases & Debits 250.00",
        "Payments & Credits 100.00CR",
        "Total Due 1,150.00",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "14 Nov 11 Nov Grocery Store City PH 200.00",
        "15 Nov 13 Nov Service Fee Reversal 100.00CR",
        "16 Nov 14 Nov Coffee Shop PH 50.00",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_statement",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 3
    assert result.summary.reconciliation_status == "matched"
    assert result.reconciliation.status == "matched"
    assert result.summary.debit_total == 250.00
    assert result.summary.credit_total == 100.00
    assert {table.table_id for table in result.document_tables} >= {
        "document_summary",
        "statement_summary",
        "transactions",
        "entities_references",
        "findings",
    }
    assert len(next(table for table in result.document_tables if table.table_id == "transactions").rows) == 3
    assert all("OCR_LAYOUT_ROW_RECONSTRUCTED" in candidate.reason_codes for candidate in result.transaction_candidates)


def test_layout_repair_attaches_orphan_descriptions_and_excludes_side_text():
    rows = [
        "Statement From 13 NOV 2023 to 12 DEC 2023",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "JIANG NAN FOOD MAKATI",
        "22 Nov 19 Nov a H 2,935.80",
        "PH",
        "by paying more than the minimum amount each month.",
        "21 Nov 19 Nov PAID THRU ONLINE BANKING 61,586.10 CR",
        "Cashback Program",
        "30 Nov 28 Nov Philippines PH 1,200.00 CR",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_repair",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 3
    assert descriptions[0] == "JIANG NAN FOOD MAKATI PH"
    assert descriptions[1] == "PAID THRU ONLINE BANKING"
    assert "by paying" not in descriptions[1]
    assert descriptions[2] == "Cashback Program Philippines PH"
    assert result.transaction_candidates[1].direction == "credit"
    assert result.transaction_candidates[2].direction == "credit"
    assert "DESCRIPTION_PREFIX_REPAIRED" in result.transaction_candidates[0].reason_codes
    assert "DESCRIPTION_SUFFIX_REPAIRED" in result.transaction_candidates[0].reason_codes
    assert any("SIDE_COLUMN_TEXT_EXCLUDED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert "CREDIT_MARKER_REPAIRED" in result.transaction_candidates[2].reason_codes


def test_layout_repair_keeps_only_nearest_orphan_prefix():
    rows = [
        "Statement From 01 JAN 2026 to 31 JAN 2026",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "Old Section Label",
        "Nearest Merchant Name",
        "02 Jan 01 Jan a H 100.00",
        "Second Merchant",
        "03 Jan 02 Jan b H 200.00",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_prefix_guard",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]

    assert result.summary.transaction_candidate_count == 2
    assert descriptions[0] == "Nearest Merchant Name"
    assert "Old Section Label" not in descriptions[0]
    assert descriptions[1] == "Second Merchant"


def test_layout_repair_ignores_side_summary_amount_on_transaction_row():
    rows = [
        "Statement From 01 JAN 2026 to 31 JAN 2026",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "04 Jan 03 Jan Table Merchant City PH 3,609.62 Payments & Credits 65,286.10CR",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_side_amount_guard",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 3609.62
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].description == "Table Merchant City PH"
    assert "SIDE_COLUMN_TEXT_EXCLUDED" in result.transaction_candidates[0].reason_codes


def test_layout_repair_pairs_split_credit_marker_with_transaction_amount():
    rows = [
        "Statement From 01 JAN 2026 to 31 JAN 2026",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "05 Jan 04 Jan Generic Cashback Program 1,200.00 CR",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_credit_marker_guard",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 1200.00
    assert result.transaction_candidates[0].direction == "credit"
    assert "CREDIT_MARKER_REPAIRED" in result.transaction_candidates[0].reason_codes


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
    assert result.summary.reference_candidate_count == 1
    assert result.reference_candidates[0].reference_type == "confirmation_number"


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


def test_statement_summary_block_is_not_misclassified_as_transaction(generic_statement_summary_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="unknown",
            text=generic_statement_summary_text,
        )
    )

    field_names = {field.field_name for field in result.financial_field_candidates}
    section_labels = {section.section_label for section in result.section_candidates}

    assert result.summary.transaction_candidate_count == 0
    assert "total_amount_due" in field_names
    assert "minimum_amount_due" in field_names
    assert "statement_summary" in section_labels
    assert result.evaluation.finding_counts["NON_TRANSACTION_FINANCIAL_BLOCK"] == 1


def test_line_item_extraction_can_be_disabled():
    text = "Tax Invoice no.: 12345\nConsultation Fee $25.00\nTotal GST $3.26"

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="invoice",
            text=text,
            options={"enable_line_items": False},
        )
    )

    assert result.summary.line_item_candidate_count == 0
    assert result.line_item_candidates == []
