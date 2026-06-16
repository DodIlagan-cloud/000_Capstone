"""M7 - Transaction Extraction Module Start
Verifies transaction and financial field candidate extraction behavior.
M7 End"""

import sys
import json
import inspect
from types import SimpleNamespace
from pathlib import Path

import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "transaction-extraction-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
module_root_path = str(MODULE_ROOT)
if module_root_path in sys.path:
    sys.path.remove(module_root_path)
sys.path.insert(0, module_root_path)

from app.models.extraction import TransactionExtractionRequest
from app.models.extraction import FinancialFieldCandidate, SourceReference, TransactionCandidate
from app.services import transaction_classification_service
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


def _word_blocks_from_positioned_rows(positioned_rows):
    blocks = []
    for positioned_row in positioned_rows:
        y, row, *position = positioned_row
        x = position[0] if position else 10
        confidence = position[1] if len(position) > 1 else 90.0
        for token in row.split():
            blocks.append(
                {
                    "page_number": 1,
                    "text": token,
                    "confidence": confidence,
                    "x": x,
                    "y": y,
                    "width": max(8, len(token) * 7),
                    "height": 12,
                }
            )
            x += max(8, len(token) * 7) + 8
    return blocks


def _word_block(text, x, y, confidence=90.0):
    return {
        "page_number": 1,
        "text": text,
        "confidence": confidence,
        "x": x,
        "y": y,
        "width": max(8, len(text) * 7),
        "height": 12,
    }


def _active_recognition_settings_payload() -> dict:
    config_dir = Path(__file__).resolve().parents[3] / "config"
    return {
        "transaction_vocabulary": json.loads((config_dir / "transaction-classification.vocabulary.json").read_text(encoding="utf-8")),
        "transaction_rules": json.loads((config_dir / "transaction-classification.rules.json").read_text(encoding="utf-8")),
        "spending_vocabulary": json.loads((config_dir / "spending-category.vocabulary.json").read_text(encoding="utf-8")),
        "spending_rules": json.loads((config_dir / "spending-category.rules.json").read_text(encoding="utf-8")),
    }


@pytest.fixture(autouse=True)
def m9_active_recognition_settings(monkeypatch):
    transaction_classification_service._clear_settings_cache()
    monkeypatch.setattr(transaction_classification_service, "_load_active_settings", lambda: _active_recognition_settings_payload())
    yield
    transaction_classification_service._clear_settings_cache()


def test_missing_text_fails_with_explicit_finding():
    result = extract_transactions(TransactionExtractionRequest(text="", document_type="statement"))

    assert result.status == "failed"
    assert result.summary.transaction_candidate_count == 0
    assert result.evaluation.finding_counts["MISSING_TEXT"] == 1


def test_transaction_classification_requires_m9_active_settings(monkeypatch):
    monkeypatch.setattr(transaction_classification_service, "_load_active_settings", lambda: None)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="payment_proof",
            text="Transfer successful confirmation no ABC123 transfer amount PHP 125.00",
        )
    )

    assert result.summary.transaction_candidate_count == 1
    candidate = result.transaction_candidates[0]
    assert candidate.transaction_type == "unknown"
    assert candidate.spending_category == "uncategorized"
    assert candidate.classification_review_required is True
    assert "RECOGNITION_SETTINGS_UNAVAILABLE" in result.evaluation.finding_counts


def test_generic_statement_table_extracts_transaction_and_financial_candidates(generic_statement_table_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_test",
            document_type="statement",
            text=generic_statement_table_text,
        )
    )

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.parse_id == "parse_test"
    assert result.summary.transaction_candidate_count == 1
    assert result.summary.financial_field_candidate_count >= 4
    assert result.summary.section_candidate_count >= 1
    assert result.summary.amount_total == 2345.67
    assert {candidate.direction for candidate in result.transaction_candidates} == {"debit"}
    assert "total_amount_due" in {field.field_name for field in result.financial_field_candidates}
    assert {section.section_label for section in result.section_candidates} >= {"statement_summary", "transaction_table"}
    assert result.financial_field_candidates[0].source.source_text_redacted
    assert result.evaluation.transaction_candidate_count == 1


def test_generic_split_statement_table_rows_are_reconstructed(generic_split_statement_table_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_split_table",
            document_type="unknown",
            text=generic_split_statement_table_text,
        )
    )

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 2
    assert [candidate.date_text for candidate in result.transaction_candidates] == [
        "November 7 2023",
        "November 7 2023",
    ]
    fields = {field.field_name: field for field in result.financial_field_candidates}
    assert fields["payments_and_credits"].normalized_value == "77803.97"
    assert "STATEMENT_PAYMENT_CREDIT_FIELD" in fields["payments_and_credits"].reason_codes
    assert result.transaction_candidates[0].description == "Keds - Sm Megamall MA: 02/03"
    assert result.transaction_candidates[1].description == "Credit-To-Cash 2-Reg: 34/36"
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
    assert result.summary.transaction_candidate_count == 2
    assert [candidate.date_text for candidate in result.transaction_candidates] == [
        "November 7 2023",
        "November 7 2023",
    ]
    assert [candidate.posted_date_text for candidate in result.transaction_candidates] == [
        "November 7 2023",
        "November 7 2023",
    ]
    assert "Credit Limit" not in {candidate.description for candidate in result.transaction_candidates}
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].description == "Credit-To-Cash 2-Reg: 34/36"
    assert result.transaction_candidates[1].amount == 12559.94
    fields = {field.field_name: field for field in result.financial_field_candidates}
    assert fields["payments_and_credits"].normalized_value == "77803.97"


def test_statement_installment_purchase_principal_is_reviewable_not_transaction():
    text = "\n".join(
        [
            "STATEMENT DATE DECEMBER 08, 2019",
            "PAYMENT DUE DATE JANUARY 1, 2020",
            "TOTAL AMOUNT DUE 6,225.25",
            "Transaction Post Date Description Amount",
            "Date",
            "November 18 November 18 Payment - Thank You -30,342.75",
            "Previous Balance 30,342.75",
            "Installment Purchase:",
            "November 21 November 25 Electronics Store Megamall 31,998.00",
            "Installment Amortization:",
            "December 6 December 6 Electronics Store Me: 01/12 2,666.50",
            "December 6 December 6 Digital Store Qu: 07/24 1,978.75",
            "November 10 November 12 Restaurant Mandaluyong 1,580.00",
        ]
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="statement", text=text))

    descriptions = {candidate.description for candidate in result.transaction_candidates}
    fields = {field.field_name: field for field in result.financial_field_candidates}

    assert result.summary.transaction_candidate_count == 3
    assert result.summary.installment_candidate_count == 1
    assert "Payment - Thank You" not in descriptions
    assert "Electronics Store Megamall" not in descriptions
    assert "Electronics Store Me: 01/12" in descriptions
    assert fields["payments_and_credits"].normalized_value == "30342.75"
    assert result.installment_candidates[0].description == "Electronics Store Megamall"
    assert result.installment_candidates[0].principal_amount == 31998.00
    assert result.installment_candidates[0].source.section_label == "installment_balances"
    assert "INSTALLMENT_PURCHASE_PRINCIPAL" in result.installment_candidates[0].reason_codes
    assert result.reconciliation.status == "matched"


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
    assert result.summary.transaction_candidate_count >= 2
    assert {candidate.source.section_label for candidate in result.transaction_candidates} == {"transaction_table"}
    assert all("OCR_FLATTENED_ROW_RECONSTRUCTED" in candidate.reason_codes for candidate in result.transaction_candidates)
    fields = {field.field_name: field for field in result.financial_field_candidates}
    assert fields["payments_and_credits"].normalized_value == "61586.10"


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


def test_layout_region_extracts_scanned_two_column_statement_table():
    blocks = [
        _word_block("Previous", 610, 30),
        _word_block("Statement", 675, 30),
        _word_block("Balance", 750, 30),
        _word_block("3,225.00", 830, 30),
        _word_block("POST", 40, 80),
        _word_block("DATE", 78, 80),
        _word_block("TRAN", 140, 80),
        _word_block("DATE", 180, 80),
        _word_block("DESCRIPTION", 250, 80),
        _word_block("AMOUNT(PHP)", 560, 80),
        _word_block("14", 40, 110),
        _word_block("May", 62, 110),
        _word_block("10", 140, 110),
        _word_block("May", 162, 110),
        _word_block("GHL*MISTER", 250, 110),
        _word_block("KABAB", 330, 110),
        _word_block("QUEZON", 386, 110),
        _word_block("CITY", 446, 110),
        _word_block("Payment", 520, 110),
        _word_block("500.00", 560, 110),
        _word_block("Due", 610, 110),
        _word_block("Date", 640, 110),
        _word_block("03", 700, 110),
        _word_block("Jul", 724, 110),
        _word_block("2019", 754, 110),
        _word_block("15", 40, 130),
        _word_block("May", 62, 130),
        _word_block("10", 140, 130),
        _word_block("May", 162, 130),
        _word_block("STARBUCKS", 250, 130),
        _word_block("UP", 330, 130),
        _word_block("NORTH", 356, 130),
        _word_block("Minimum", 520, 130),
        _word_block("125.00", 560, 130),
        _word_block("Payment", 610, 130),
        _word_block("500.00", 700, 130),
        _word_block("16", 40, 150),
        _word_block("May", 62, 150),
        _word_block("14", 140, 150),
        _word_block("May", 162, 150),
        _word_block("GHL*MISTER", 250, 150),
        _word_block("KABAB", 330, 150),
        _word_block("Available", 520, 150),
        _word_block("670.00", 560, 150),
        _word_block("Credit", 610, 150),
        _word_block("187,911.26", 680, 150),
        _word_block("20", 40, 170),
        _word_block("May", 62, 170),
        _word_block("16", 140, 170),
        _word_block("May", 162, 170),
        _word_block("AVENETO", 250, 170),
        _word_block("PIZZERIA", 315, 170),
        _word_block("Previous", 520, 170),
        _word_block("2,026.60", 560, 170),
        _word_block("Statement", 630, 170),
        _word_block("Balance", 710, 170),
        _word_block("3,225.00", 790, 170),
        _word_block("22", 40, 190),
        _word_block("May", 62, 190),
        _word_block("20", 140, 190),
        _word_block("May", 162, 190),
        _word_block("PANCAKE", 250, 190),
        _word_block("HOUSE", 320, 190),
        _word_block("Purchases", 520, 190),
        _word_block("767.14", 560, 190),
        _word_block("&", 625, 190),
        _word_block("Debits", 650, 190),
        _word_block("4,088.74", 710, 190),
        _word_block("03", 40, 210),
        _word_block("Jun", 62, 210),
        _word_block("31", 140, 210),
        _word_block("May", 162, 210),
        _word_block("PAID", 250, 210),
        _word_block("THRU", 292, 210),
        _word_block("BPI", 338, 210),
        _word_block("OBP", 375, 210),
        _word_block("Total", 520, 210),
        _word_block("3,225.00CR", 560, 210),
        _word_block("Account", 650, 210),
        _word_block("Balance", 720, 210),
        _word_block("4,088.74", 790, 210),
        _word_block("Please", 40, 310),
        _word_block("detach", 90, 310),
        _word_block("payment", 145, 310),
        _word_block("slip", 205, 310),
        _word_block("Payment", 250, 330),
        _word_block("Due", 320, 330),
        _word_block("Date", 350, 330),
        _word_block("03", 395, 330),
        _word_block("Jul", 420, 330),
        _word_block("2019", 450, 330),
    ]
    text = (
        "Statement From 13 MAY 2019 to 12 JUN 2019 Previous Statement Balance 3,225.00 "
        "Payments & Credits 3,225.00CR Purchases & Debits 4,088.74 Total Due 4,088.74 "
        "Payment Due Date 03 Jul 2019 POST DATE TRAN DATE DESCRIPTION AMOUNT(PHP)"
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_scanned_region_statement",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]
    fields = [field for field in result.financial_field_candidates if field.field_name == "payments_and_credits"]

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 5
    assert result.summary.debit_total == 4088.74
    assert result.reconciliation.status == "matched"
    assert descriptions == [
        "GHL*MISTER KABAB QUEZON CITY",
        "STARBUCKS UP NORTH",
        "GHL*MISTER KABAB",
        "AVENETO PIZZERIA",
        "PANCAKE HOUSE",
    ]
    assert any(field.normalized_value == "3225.00" for field in fields)
    assert all("OCR_STATEMENT_REGION_DETECTED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert all("OCR_STATEMENT_REGION_EXCLUDED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert all("payment due date" not in candidate.source.text.lower() for candidate in result.transaction_candidates)
    assert all("please detach" not in candidate.source.text.lower() for candidate in result.transaction_candidates)


def test_layout_region_clips_all_pages_when_interference_on_any_page():
    p1_blocks = [
        _word_block("POST", 40, 80),
        _word_block("DATE", 78, 80),
        _word_block("TRAN", 140, 80),
        _word_block("DATE", 180, 80),
        _word_block("DESCRIPTION", 250, 80),
        _word_block("AMOUNT(PHP)", 560, 80),
        _word_block("14", 40, 110),
        _word_block("May", 62, 110),
        _word_block("10", 140, 110),
        _word_block("May", 162, 110),
        _word_block("MERCHANT", 250, 110),
        _word_block("ONE", 370, 110),
        _word_block("Credit", 520, 110),
        _word_block("100.00", 560, 110),
        _word_block("Limit", 620, 110),
        _word_block("Please", 40, 310),
        _word_block("detach", 90, 310),
        _word_block("payment", 145, 310),
        _word_block("slip", 205, 310),
    ]
    p2_blocks = [
        _word_block("POST", 40, 80),
        _word_block("DATE", 78, 80),
        _word_block("TRAN", 140, 80),
        _word_block("DATE", 180, 80),
        _word_block("DESCRIPTION", 250, 80),
        _word_block("AMOUNT(PHP)", 560, 80),
        _word_block("20", 40, 110),
        _word_block("May", 62, 110),
        _word_block("18", 140, 110),
        _word_block("May", 162, 110),
        _word_block("MERCHANT", 250, 110),
        _word_block("TWO", 370, 110),
        _word_block("Credit", 520, 110),
        _word_block("200.00", 560, 110),
        _word_block("Limit", 620, 110),
        _word_block("22", 40, 130),
        _word_block("May", 62, 130),
        _word_block("20", 140, 130),
        _word_block("May", 162, 130),
        _word_block("MERCHANT", 250, 130),
        _word_block("THREE", 370, 130),
        _word_block("Credit", 520, 130),
        _word_block("300.00", 560, 130),
        _word_block("Limit", 620, 130),
    ]
    text = "POST DATE TRAN DATE DESCRIPTION AMOUNT(PHP)"

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_multipage_region",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[
                {"page_number": 1, "text": text, "ocr_word_blocks": p1_blocks},
                {"page_number": 2, "text": text, "ocr_word_blocks": p2_blocks},
            ],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]
    assert result.status != "failed"
    assert result.summary.transaction_candidate_count == 3
    assert "MERCHANT ONE" in descriptions
    assert "MERCHANT TWO" in descriptions
    assert "MERCHANT THREE" in descriptions
    assert all("OCR_STATEMENT_REGION_DETECTED" in c.reason_codes for c in result.transaction_candidates)


def test_layout_region_stray_amount_row_does_not_overwrite_transaction_amount():
    # PAID THRU BPI OBP has amount 3,225.00 CR (correct).
    # A separate OCR line at y=130 carries only the side-column summary total 4,088.74.
    # Without the region-mode follow_up_amount guard that line would overwrite the correct amount.
    blocks = [
        _word_block("POST", 40, 80),
        _word_block("DATE", 78, 80),
        _word_block("TRAN", 140, 80),
        _word_block("DATE", 180, 80),
        _word_block("DESCRIPTION", 250, 80),
        _word_block("AMOUNT(PHP)", 560, 80),
        _word_block("03", 40, 110),
        _word_block("Jun", 62, 110),
        _word_block("31", 140, 110),
        _word_block("May", 162, 110),
        _word_block("PAID", 250, 110),
        _word_block("THRU", 292, 110),
        _word_block("BPI", 338, 110),
        _word_block("OBP", 375, 110),
        _word_block("3,225.00", 560, 110),
        _word_block("CR", 610, 110),
        _word_block("4,088.74", 560, 130),
        _word_block("Please", 40, 310),
        _word_block("detach", 90, 310),
        _word_block("payment", 145, 310),
        _word_block("slip", 205, 310),
    ]
    text = "POST DATE TRAN DATE DESCRIPTION AMOUNT(PHP)"

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_stray_amount",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    payment_fields = [f for f in result.financial_field_candidates if f.field_name == "payments_and_credits"]
    assert result.summary.transaction_candidate_count == 0
    assert any(f.normalized_value == "3225.00" for f in payment_fields)


def test_layout_region_candidates_do_not_replace_richer_legacy_extraction():
    prefer_region = extract_transactions.__globals__["_prefer_layout_region_candidates"]
    region_candidates = [SimpleNamespace(amount=4088.74)]
    legacy_candidates = [
        SimpleNamespace(amount=500.00),
        SimpleNamespace(amount=125.00),
        SimpleNamespace(amount=670.00),
        SimpleNamespace(amount=2026.60),
        SimpleNamespace(amount=767.14),
        SimpleNamespace(amount=3225.00),
    ]

    assert prefer_region(region_candidates, legacy_candidates) is False


def test_ocr_grid_extracts_hsbc_compact_dates_without_clean_description_header():
    blocks = [
        _word_block("POST", 114, 360),
        _word_block("TRAN", 223, 360),
        _word_block("pots", 900, 360),
        _word_block("pared", 980, 360),
        _word_block("Previous", 782, 462),
        _word_block("Statement", 866, 462),
        _word_block("Balance", 970, 462),
        _word_block("3,225.00", 1080, 462),
        _word_block("14", 119, 508),
        _word_block("May", 142, 508),
        _word_block("10May", 222, 508),
        _word_block("GHL*MISTER", 298, 508),
        _word_block("KABAB-U.P", 386, 508),
        _word_block("QUEZON", 472, 508),
        _word_block("CITY", 536, 508),
        _word_block("500.00", 682, 508),
        _word_block("ACCOUNT", 783, 508),
        _word_block("SUMMARY", 890, 508),
        _word_block("Previous", 993, 508),
        _word_block("Statement", 1075, 508),
        _word_block("Balance", 1168, 508),
        _word_block("3,225.00", 1255, 508),
        _word_block("15", 119, 567),
        _word_block("May", 142, 567),
        _word_block("10", 222, 567),
        _word_block("May", 244, 567),
        _word_block("OS", 298, 567),
        _word_block("NORTH", 335, 567),
        _word_block("125.00", 683, 567),
        _word_block("Purchases", 785, 567),
        _word_block("&", 876, 567),
        _word_block("Debits", 903, 567),
        _word_block("4,088.74", 966, 567),
        _word_block("20May", 119, 680),
        _word_block("16", 222, 680),
        _word_block("May", 245, 680),
        _word_block("AVENETOPIZZERIA", 298, 680),
        _word_block("QUEZON", 432, 680),
        _word_block("2,026.60", 666, 680),
        _word_block("_Payment", 783, 680),
        _word_block("Due", 868, 680),
        _word_block("Date", 910, 680),
        _word_block("03", 957, 680),
        _word_block("Jul", 982, 680),
        _word_block("2019", 1018, 680),
        _word_block("22", 119, 724),
        _word_block("May", 142, 724),
        _word_block("20", 222, 724),
        _word_block("May", 245, 724),
        _word_block("PANCAKE", 298, 724),
        _word_block("HOUSE", 375, 724),
        _word_block("767.14", 684, 724),
        _word_block("03", 119, 786),
        _word_block("Jun", 142, 786),
        _word_block("31", 222, 786),
        _word_block("May", 245, 786),
        _word_block("PAID", 298, 786),
        _word_block("THRU", 344, 786),
        _word_block("BPI", 390, 786),
        _word_block("OBP", 430, 786),
        _word_block("3,225.00CR", 665, 786),
        _word_block("CREDIT", 782, 786),
        _word_block("LIMIT", 850, 786),
        _word_block("AND", 910, 786),
        _word_block("INTEREST", 955, 786),
        _word_block("RATES", 1040, 786),
    ]
    text = (
        "Statement From 13 MAY 2019 to 12 JUN 2019 Previous Statement Balance 3,225.00 "
        "Payments & Credits 3,225.00CR Purchases & Debits 4,088.74 Total Due 4,088.74 "
        "POST TRAN"
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_hsbc_grid_statement",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]
    fields = [field for field in result.financial_field_candidates if field.field_name == "payments_and_credits"]

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 4
    assert result.summary.debit_total == 3418.74
    assert result.evaluation.finding_counts["STATEMENT_PURCHASE_TOTAL_MISMATCH"] == 1
    assert descriptions == [
        "GHL*MISTER KABAB-U.P QUEZON CITY",
        "OS NORTH",
        "AVENETOPIZZERIA QUEZON",
        "PANCAKE HOUSE",
    ]
    assert any(field.normalized_value == "3225.00" for field in fields)
    assert all("OCR_TABLE_GRID_ROW_RECONSTRUCTED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert all("Purchases" not in candidate.source.text for candidate in result.transaction_candidates)
    assert all("Payment Due Date" not in candidate.source.text for candidate in result.transaction_candidates)


def test_ocr_grid_does_not_treat_repost_transportation_description_as_header():
    blocks = [
        _word_block("POST", 114, 360),
        _word_block("TRAN", 223, 360),
        _word_block("14", 119, 508),
        _word_block("Nov", 142, 508),
        _word_block("11", 222, 508),
        _word_block("Nov", 245, 508),
        _word_block("REPOST", 298, 508),
        _word_block("TRANSPORTATION", 360, 508),
        _word_block("SERVICES", 480, 508),
        _word_block("100.00", 682, 508),
        _word_block("15", 119, 548),
        _word_block("Nov", 142, 548),
        _word_block("14", 222, 548),
        _word_block("Nov", 245, 548),
        _word_block("SECOND", 298, 548),
        _word_block("MERCHANT", 360, 548),
        _word_block("200.00", 682, 548),
        _word_block("16", 119, 588),
        _word_block("Nov", 142, 588),
        _word_block("15", 222, 588),
        _word_block("Nov", 245, 588),
        _word_block("THIRD", 298, 588),
        _word_block("MERCHANT", 360, 588),
        _word_block("300.00", 682, 588),
    ]
    text = "Statement From 01 NOV 2023 to 30 NOV 2023 POST TRAN Purchases & Debits 600.00"

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]

    assert result.summary.transaction_candidate_count == 3
    assert "REPOST TRANSPORTATION SERVICES" in descriptions


def test_ocr_grid_foreign_currency_row_uses_rightmost_billing_amount():
    blocks = [
        _word_block("POST", 114, 360),
        _word_block("TRAN", 223, 360),
        _word_block("24", 119, 508),
        _word_block("Sep", 142, 508),
        _word_block("25", 222, 508),
        _word_block("Sep", 245, 508),
        _word_block("KLOOK", 298, 508),
        _word_block("TECHNOLOGY", 360, 508),
        _word_block("USD", 540, 508),
        _word_block("30.98", 610, 508),
        _word_block("1,711.05", 682, 508),
        _word_block("03", 119, 548),
        _word_block("Oct", 142, 548),
        _word_block("05", 222, 548),
        _word_block("Oct", 245, 548),
        _word_block("LAKGOJAE", 298, 548),
        _word_block("KRW", 540, 548),
        _word_block("180,000.00", 600, 548),
        _word_block("8,849.47", 700, 548),
        _word_block("10", 119, 588),
        _word_block("Oct", 142, 588),
        _word_block("11", 222, 588),
        _word_block("Oct", 245, 588),
        _word_block("LOCAL", 298, 588),
        _word_block("MERCHANT", 360, 588),
        _word_block("500.00", 682, 588),
    ]
    text = "Statement From 01 SEP 2018 to 31 OCT 2018 POST TRAN Purchases & Debits 11,060.52"

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    by_description = {candidate.description: candidate for candidate in result.transaction_candidates}

    assert by_description["KLOOK TECHNOLOGY USD"].amount == 1711.05
    assert by_description["LAKGOJAE KRW"].amount == 8849.47


def test_ocr_grid_keeps_continuation_page_rows_without_repeated_header():
    extract_grid = extract_transactions.__globals__["_extract_ocr_statement_grid_rows"]

    def block(text, x):
        return SimpleNamespace(text=text, x=x, width=max(8, len(text) * 7), confidence=90.0)

    rows = [
        {"page_number": 1, "line_number": 1, "text": "POST TRAN", "confidence": 0.9, "blocks": [block("POST", 114), block("TRAN", 223)]},
        {
            "page_number": 1,
            "line_number": 2,
            "text": "14 May 10 May MERCHANT ONE 100.00",
            "confidence": 0.9,
            "blocks": [block("14", 119), block("May", 142), block("10", 222), block("May", 245), block("MERCHANT", 298), block("ONE", 370), block("100.00", 682)],
        },
        {
            "page_number": 1,
            "line_number": 3,
            "text": "15 May 11 May MERCHANT TWO 200.00",
            "confidence": 0.9,
            "blocks": [block("15", 119), block("May", 142), block("11", 222), block("May", 245), block("MERCHANT", 298), block("TWO", 370), block("200.00", 682)],
        },
        {
            "page_number": 3,
            "line_number": 4,
            "text": "16 May 12 May MERCHANT THREE 300.00",
            "confidence": 0.9,
            "blocks": [block("16", 119), block("May", 142), block("12", 222), block("May", 245), block("MERCHANT", 298), block("THREE", 370), block("300.00", 682)],
        },
    ]

    candidates = extract_grid(rows, "statement", 2019)

    assert [candidate.description for candidate in candidates] == [
        "MERCHANT ONE",
        "MERCHANT TWO",
        "MERCHANT THREE",
    ]


def test_hsbc_damaged_ocr_row_repairs_missing_purchase_from_statement_total():
    blocks = [
        _word_block("POST", 114, 348),
        _word_block("TRAN", 223, 348),
        _word_block("pnts", 785, 348),
        _word_block("Previous", 298, 454),
        _word_block("Statement", 365, 454),
        _word_block("Balance", 441, 454),
        _word_block("5,165.00", 667, 454),
        _word_block("83", 119, 503, 60),
        _word_block("jun", 145, 503, 83),
        _word_block("00", 221, 503, 68),
        _word_block("J", 243, 503, 57),
        _word_block("lun", 252, 507, 50),
        _word_block("THE", 297, 493),
        _word_block("MANDALUYONG", 298, 503, 61),
        _word_block("FRENCH", 335, 493),
        _word_block("BAKER", 406, 493),
        _word_block("PH", 438, 503, 69),
        _word_block("3F", 468, 493, 84),
        _word_block("498.00", 683, 503, 76),
        _word_block("ACCOUNT", 783, 481),
        _word_block("Previous", 785, 503),
        _word_block("Statement", 860, 503),
        _word_block("SUMMARY", 893, 503),
        _word_block("Balance", 950, 503),
        _word_block("5,165.00", 1076, 503),
        _word_block("18", 119, 550),
        _word_block("Jun", 141, 550),
        _word_block("18", 222, 550),
        _word_block("Jun", 245, 550, 70),
        _word_block("PAID", 298, 550, 70),
        _word_block("THRU", 341, 550),
        _word_block("BPI", 394, 550, 89),
        _word_block("OBP", 426, 550),
        _word_block("5,165.00CR", 665, 550),
        _word_block("Purchases", 785, 558),
        _word_block("&", 875, 558),
        _word_block("Debits", 894, 558),
        _word_block("5,358.00", 1076, 558),
        _word_block("12", 119, 596),
        _word_block("2a", 126, 596, 21),
        _word_block("Jul", 157, 596),
        _word_block("12", 222, 596),
        _word_block("2", 229, 596, 29),
        _word_block("ul", 247, 592, 29),
        _word_block("Jul", 261, 596),
        _word_block("JSFIVE10", 297, 586),
        _word_block("OF", 298, 596, 47),
        _word_block("6", 333, 596, 76),
        _word_block("INSTALLMENTS", 347, 596, 82),
        _word_block("VENTURES-QUEZ", 374, 586),
        _word_block("4TH", 516, 586),
        _word_block("5,165.00", 669, 596),
        _word_block("Total", 783, 596),
        _word_block("Outstanding", 784, 596),
        _word_block("Account", 832, 596, 89),
        _word_block("Installments.", 889, 596, 89),
        _word_block("Balance", 909, 596),
        _word_block("15,688.00", 1064, 596),
        _word_block("10,330.00", 1068, 596),
        _word_block("Total", 298, 640),
        _word_block("Due", 373, 640),
        _word_block("5,358.00", 633, 638),
    ]
    text = (
        "Statement From 13 Jun 2018 to 12 Jul 2018 "
        "Previous Statement Balance 5,165.00 Payments & Credits 5,165.00CR "
        "Purchases & Debits 5,358.00 Total Due 5,358.00 POST TRAN"
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]
    amounts = [candidate.amount for candidate in result.transaction_candidates]

    assert result.summary.transaction_candidate_count == 2
    assert result.reconciliation.status == "matched"
    assert amounts == [193.0, 5165.0]
    assert any("FRENCH BAKER" in description for description in descriptions)
    assert any("JSFIVE10" in description for description in descriptions)
    assert all("PAID THRU" not in description for description in descriptions)
    repaired = next(candidate for candidate in result.transaction_candidates if candidate.amount == 193.0)
    assert "AMOUNT_REPAIRED_FROM_STATEMENT_TOTAL" in repaired.reason_codes
    assert "OCR_DAMAGED_TRANSACTION_ROW_REPAIRED" in result.evaluation.finding_counts


def test_reconciliation_repair_preserves_non_debit_candidates(monkeypatch):
    repair = extract_transactions.__globals__["_repair_statement_purchase_gap_transactions"]
    service_globals = extract_transactions.__globals__
    source = SourceReference(
        page_number=1,
        line_number=1,
        text="source",
        section_id="section_1_transaction_table",
        section_label="transaction_table",
        source_text_redacted="source",
    )
    original_debit = TransactionCandidate(
        candidate_id="txn_0001",
        date_text="01 May 2019",
        description="Damaged debit",
        amount=999.00,
        currency="PHP",
        direction="debit",
        source=source,
        confidence=0.7,
    )
    original_credit = TransactionCandidate(
        candidate_id="txn_0002",
        date_text="02 May 2019",
        description="Merchant refund",
        amount=25.00,
        currency="PHP",
        direction="credit",
        source=source,
        confidence=0.9,
    )
    repaired_debit = TransactionCandidate(
        candidate_id="txn_0001",
        date_text="01 May 2019",
        description="Repaired purchase",
        amount=100.00,
        currency="PHP",
        direction="debit",
        source=source,
        confidence=0.9,
    )
    fields = [
        FinancialFieldCandidate(
            field_name="purchases_and_debits",
            value_type="amount",
            value_text="100.00",
            normalized_value="100.00",
            currency="PHP",
            source=source,
            confidence=0.9,
        )
    ]
    monkeypatch.setitem(service_globals, "_layout_rows", lambda request: [{"text": "row"}])
    monkeypatch.setitem(service_globals, "_hsbc_reconciliation_repair_rows", lambda **kwargs: [repaired_debit])

    repaired = repair(
        request=TransactionExtractionRequest(document_type="statement", text="statement"),
        transactions=[original_debit, original_credit],
        fields=fields,
        document_type="statement",
        line_refs=[],
    )

    assert [candidate.description for candidate in repaired] == ["Repaired purchase", "Merchant refund"]
    assert [candidate.candidate_id for candidate in repaired] == ["txn_0001", "txn_0002"]


def test_ocr_grid_rejects_impossible_day_month_dates():
    blocks = [
        _word_block("POST", 114, 360),
        _word_block("TRAN", 223, 360),
        _word_block("14", 119, 508),
        _word_block("Nov", 142, 508),
        _word_block("11", 222, 508),
        _word_block("Nov", 245, 508),
        _word_block("VALID", 298, 508),
        _word_block("MERCHANT", 360, 508),
        _word_block("100.00", 682, 508),
        _word_block("47", 119, 548),
        _word_block("Nov", 142, 548),
        _word_block("14", 222, 548),
        _word_block("Nov", 245, 548),
        _word_block("BAD", 298, 548),
        _word_block("DATE", 340, 548),
        _word_block("149.00", 682, 548),
        _word_block("15", 119, 588),
        _word_block("Nov", 142, 588),
        _word_block("14", 222, 588),
        _word_block("Nov", 245, 588),
        _word_block("ANOTHER", 298, 588),
        _word_block("MERCHANT", 370, 588),
        _word_block("200.00", 682, 588),
        _word_block("16", 119, 628),
        _word_block("Nov", 142, 628),
        _word_block("15", 222, 628),
        _word_block("Nov", 245, 628),
        _word_block("THIRD", 298, 628),
        _word_block("MERCHANT", 360, 628),
        _word_block("300.00", 682, 628),
    ]
    text = "Statement From 01 NOV 2023 to 30 NOV 2023 POST TRAN Purchases & Debits 600.00"

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    assert result.summary.transaction_candidate_count == 3
    assert result.summary.debit_total == 600.00
    assert all(candidate.date_text != "47 Nov 2023" for candidate in result.transaction_candidates)


def test_amount_pattern_accepts_trailing_sentence_period_and_three_decimal_ocr():
    amounts = extract_transactions.__globals__["_amounts"]

    assert amounts("paid 99.50.") == [("PHP", 99.50)]
    assert amounts("OCR total 1234.567") == [("PHP", 1234.567)]
    assert amounts("malformed 3.225.00") == []
    assert amounts("malformed 1,234,56") == []


def test_layout_statement_foreign_currency_row_uses_billing_amount():
    rows = [
        "Statement From 13 SEP 2018 to 14 OCT 2018",
        "Previous Statement Balance 7,155.00",
        "Payments & Credits 7,155.00CR",
        "Purchases & Debits 3,707.82",
        "Total Due 3,707.82",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "02 Oct 29 Sep Restaurant Mandaluyong PH 1,382.51",
        "09 Oct 05 Oct Overseas Merchant KR KRW 46,750 2,325.31",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_foreign_currency",
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
    assert result.summary.transaction_candidate_count == 2
    assert result.summary.debit_total == 3707.82
    assert result.reconciliation.status == "matched"
    assert result.transaction_candidates[1].amount == 2325.31
    assert "46,750" not in result.transaction_candidates[1].description
    assert "BILLING_CURRENCY_AMOUNT_SELECTED" in result.transaction_candidates[1].reason_codes


def test_ocr_grid_extraction_uses_clipped_statement_region_when_available():
    source = inspect.getsource(extract_transactions.__globals__["_extract_layout_statement_rows"])

    assert "grid_source_rows = region_rows or rows" in source
    assert "rows=grid_source_rows" in source


def test_statement_foreign_currency_continuation_rows_are_reconstructed_from_text():
    rows = [
        "STATEMENT DATE OCTOBER 07, 2018",
        "Transaction Post Date Description Amount",
        "Date",
        "September 24 September 25 Klook Technology Hong Kong HK",
        "U.S. Dollar 30.98 1,711.05",
        "October 3 October 5 Lakgojae Andong KR",
        "Won 180,000.00 8,849.47",
        "Purchases & Debits 10,560.52",
    ]

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_bpi_foreign_currency_continuations",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text="\n".join(rows),
        )
    )

    candidates = {candidate.description: candidate for candidate in result.transaction_candidates}

    assert result.status != "failed"
    assert candidates["Klook Technology Hong Kong HK"].amount == 1711.05
    assert candidates["Lakgojae Andong KR"].amount == 8849.47
    assert candidates["Klook Technology Hong Kong HK"].date_text == "September 24 2018"
    assert candidates["Lakgojae Andong KR"].posted_date_text == "October 5 2018"
    assert "BILLING_CURRENCY_AMOUNT_SELECTED" in candidates["Klook Technology Hong Kong HK"].reason_codes
    assert "BILLING_CURRENCY_AMOUNT_SELECTED" in candidates["Lakgojae Andong KR"].reason_codes


def test_statement_continuation_row_does_not_consume_next_complete_transaction():
    rows = [
        "STATEMENT DATE OCTOBER 07, 2018",
        "Transaction Post Date Description Amount",
        "Date",
        "September 24 September 25 Klook Technology Hong Kong HK",
        "October 3 October 5 Lakgojae Andong KR 8,849.47",
        "Purchases & Debits 8,849.47",
    ]

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_bpi_continuation_next_row_guard",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text="\n".join(rows),
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]

    assert "Klook Technology Hong Kong HK" not in descriptions
    assert descriptions == ["Lakgojae Andong KR"]
    assert result.transaction_candidates[0].amount == 8849.47


def test_statement_summary_payments_and_credits_total_wins_over_payment_row():
    rows = [
        "Statement From 13 JUN 2019 to 14 JUL 2019",
        "Previous Statement Balance 4,088.74",
        "Payments & Credits 4,352.43CR",
        "Purchases & Debits 19,052.39",
        "Total Due 18,788.70",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "17 Jun 14 Jun Utility Billspay Taguig PH 5,573.70",
        "18 Jun 14 Jun Paid Thru Online Banking 4,088.74 CR",
        "28 Jun 26 Jun Cashback Program Philippines PH 263.69 CR",
        "10 Jul 07 Jul Fuel Station Quezon PH 13,478.69",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_payment_credit_summary_total",
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

    fields = [field for field in result.financial_field_candidates if field.field_name == "payments_and_credits"]

    assert result.status == "completed"
    assert len(fields) >= 2
    assert any(field.normalized_value == "4352.43" and "STATEMENT_SUMMARY_LABEL_DETECTED" in field.reason_codes for field in fields)
    assert any(field.normalized_value == "4088.74" and "STATEMENT_PAYMENT_CREDIT_FIELD" in field.reason_codes for field in fields)
    assert result.summary.debit_total == 19052.39
    assert result.summary.credit_total == 263.69
    assert result.reconciliation.credit_total == 4352.43
    assert result.reconciliation.computed_total_due == 18788.70
    assert result.reconciliation.status == "matched"


def test_paid_thru_bpi_statement_row_is_payment_credit_field_not_transaction():
    rows = [
        "Statement From 13 JUN 2018 to 12 JUL 2018",
        "Previous Statement Balance 5,165.00",
        "Payments & Credits 5,165.00CR",
        "Purchases & Debits 193.00",
        "Total Due 193.00",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "18 Jun 18 Jun PAID THRU BPI OBP 5,165.00CR",
        "13 Jun 09 Jun THE FRENCH BAKER 3F MANDALUYONG PH 193.00",
    ]
    text = "\n".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    descriptions = [candidate.description for candidate in result.transaction_candidates]
    payment_fields = [field for field in result.financial_field_candidates if field.field_name == "payments_and_credits"]

    assert result.summary.transaction_candidate_count == 1
    assert descriptions[0].startswith("THE FRENCH BAKER")
    assert "MANDALUYONG PH" in descriptions[0]
    assert any(field.normalized_value == "5165.00" for field in payment_fields)
    assert all("PAID THRU BPI" not in description for description in descriptions)
    assert result.reconciliation.status == "matched"


def test_credit_card_statement_debit_rows_classify_as_merchant_purchases_without_ai():
    rows = [
        "Statement From 13 SEP 2018 to 14 OCT 2018",
        "Previous Statement Balance 7,155.00",
        "Payments & Credits 7,155.00CR",
        "Purchases & Debits 3,707.82",
        "Total Due 3,707.82",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "17 Sep 17 Sep PAID THRU BPI OBP 7,155.00CR",
        "02 Oct 29 Sep SUPERBOWL MANDALUYONG OF CHINA PH 1,382.51",
        "09 Oct 05 Oct BUSINESS KR KRW 46,750 4524 BUSAN 2,325.31",
    ]
    text = "\n".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
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

    by_description = {candidate.description: candidate for candidate in result.transaction_candidates}
    superbowl = by_description["SUPERBOWL MANDALUYONG OF CHINA PH"]
    busan = by_description["BUSINESS KR 4524 BUSAN"]

    assert result.summary.transaction_candidate_count == 2
    assert superbowl.transaction_type == "purchase"
    assert superbowl.transaction_subtype == "merchant_purchase"
    assert superbowl.spending_category == "food_dining"
    assert superbowl.spending_subcategory == "restaurant"
    assert "CREDIT_CARD_STATEMENT_DEBIT_PURCHASE" in superbowl.transaction_type_reason_codes
    assert busan.transaction_type == "purchase"
    assert busan.transaction_subtype == "merchant_purchase"
    assert busan.spending_category == "uncategorized"
    assert busan.spending_subcategory == "unknown"
    assert result.reconciliation.status == "matched"


def test_statement_purchases_total_mismatch_adds_review_finding():
    rows = [
        "Statement From 13 MAY 2019 to 12 JUN 2019",
        "Previous Statement Balance 0.00",
        "Payments & Credits 0.00CR",
        "Purchases & Debits 600.00",
        "Total Due 600.00",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "14 May 10 May VALID MERCHANT 100.00",
        "15 May 11 May ANOTHER MERCHANT 200.00",
    ]
    text = "\n".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    assert result.reconciliation.status == "needs_review"
    assert "STATEMENT_PURCHASE_TOTAL_MISMATCH" in result.evaluation.finding_counts
    assert "PURCHASE_TOTAL_MISMATCH" in result.reconciliation.reason_codes


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

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 2
    assert descriptions[0] == "JIANG NAN FOOD MAKATI PH"
    assert descriptions[1] == "Cashback Program Philippines PH"
    assert result.transaction_candidates[1].direction == "credit"
    fields = {field.field_name: field for field in result.financial_field_candidates}
    assert fields["payments_and_credits"].normalized_value == "61586.10"
    assert "DESCRIPTION_PREFIX_REPAIRED" in result.transaction_candidates[0].reason_codes
    assert "DESCRIPTION_SUFFIX_REPAIRED" in result.transaction_candidates[0].reason_codes
    assert any("SIDE_COLUMN_TEXT_EXCLUDED" in candidate.reason_codes for candidate in result.transaction_candidates)
    assert "CREDIT_MARKER_REPAIRED" in result.transaction_candidates[1].reason_codes


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


def test_layout_repair_does_not_treat_credit_limit_side_text_as_credit_marker():
    rows = [
        "Statement From 01 JAN 2026 to 31 JAN 2026",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "06 Jan 05 Jan Online Merchant SG 149.00 CREDIT LIMIT 192,000.00",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_credit_side_text_guard",
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
    assert result.transaction_candidates[0].amount == 149.00
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].description == "Online Merchant SG"
    assert "CREDIT_MARKER_REPAIRED" not in result.transaction_candidates[0].reason_codes
    assert "SIDE_COLUMN_TEXT_EXCLUDED" in result.transaction_candidates[0].reason_codes


def test_layout_repair_extracts_vertically_split_amount_row():
    text = "\n".join(
        [
            "Statement From 01 JAN 2026 to 31 JAN 2026",
            "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
            "20 Jan 16 Jan Table Cafe City PH",
            "215.00",
        ]
    )
    blocks = _word_blocks_from_positioned_rows(
        [
            (20, "Statement From 01 JAN 2026 to 31 JAN 2026"),
            (60, "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)"),
            (100, "20 Jan 16 Jan Table Cafe City PH"),
            (110, "215.00", 520, 50.0),
        ]
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_split_amount",
            classification={
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.82,
                "status": "classified",
            },
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": blocks}],
        )
    )

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].date_text == "20 Jan 2026"
    assert result.transaction_candidates[0].posted_date_text == "16 Jan 2026"
    assert result.transaction_candidates[0].description == "Table Cafe City PH"
    assert result.transaction_candidates[0].amount == 215.00
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].source.ocr_confidence == 0.5


def test_layout_repair_does_not_attach_statement_footer_amount_to_last_row():
    rows = [
        "Statement From 01 JAN 2026 to 31 JAN 2026",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "12 Jan 12 Jan Installment Merchant 1 of 6 1,598.00",
        "Total Due 100,993.16",
        "YOUR INSTALLMENT PLAN",
    ]
    text = " ".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_layout_footer_guard",
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
    assert result.transaction_candidates[0].description == "Installment Merchant 1 of 6"
    assert result.transaction_candidates[0].amount == 1598.00
    assert result.transaction_candidates[0].direction == "debit"


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


def test_parser_payload_uses_classification_and_quality_context(proof_of_payment_text):
    result = extract_transactions(
        TransactionExtractionRequest(
            parse_id="parse_from_parser",
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
    assert result.evaluation.parse_id == "parse_from_parser"
    assert result.summary.pages_processed == 1
    assert result.summary.transaction_candidate_count == 1


def test_receipt_compact_ocr_date_is_used_for_derived_transaction():
    text = (
        "Awanui Mt Wellington TIME 18APR2026 09:35 TRAN 01016 CREDIT "
        "PURCHASE NZD227.00 TOTAL NZD227.00 APPROVED"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].date_text == "18/04/2026"
    assert result.transaction_candidates[0].amount == 227.00
    assert result.transaction_candidates[0].currency == "NZD"


def test_receipt_date_extraction_skips_impossible_ocr_numeric_date():
    text = (
        "KMART TAX INVOICE 5/68/25 15:17 TOTAL ITEMS = 6 "
        "05/08/25 15:11 TOTAL 111.00 EFTPOS NZD$111.00 APPROVED"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].date_text == "05/08/25"
    assert result.transaction_candidates[0].amount == 111.00


def test_receipt_description_prefers_san_michelle_product_over_refund_policy():
    text = (
        "Tax Invoice San Nichelle Bags Sylvia Park DATE: 24-05-2026 16:19 "
        "21000008001 /HandBag L3-1/BLACK QTY 1 @ $56.00 $56.00 "
        "1 Items TOTAL: $56.00 EFTPOS; $56.00 Refund Policy note within 14 days"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].description == "San Michelle Bags - Handbag L3-1/Black"


def test_receipt_description_prefers_bunnings_merchant_over_footer_text():
    text = (
        "GUNN IHS LTWITED Sun 31/08/2025 03:01:41 SELF CHECKOUT "
        "Total $25.54 EFT CARD Thank you for shopping with Bunnings "
        "Please retain receipt for proof of purchase"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].description == "Bunnings - Self Checkout"


def test_receipt_description_prefers_awanui_terminal_merchant_over_card_noise():
    text = (
        "Awanui Mt Wellington 37 - 41 Carbine Rd Auckland New Zealand "
        "MID 59099900 TSP 350998000001 INV# 660176047 "
        "Visa Credit PURCHASE 9m N21 227,00 /N219$227.00 APPROVED"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].description == "Awanui - Card purchase - Mt Wellington"
    assert result.transaction_candidates[0].amount == 227.00
    assert result.transaction_candidates[0].currency == "NZD"


def test_invoice_description_prefers_awunui_service_over_owing_footer():
    text = (
        "Invoice wanui Labs Auckland Issued: 18/04/2026 09:36:20 "
        "CC CRE - Creatinine $25.00 DRW - Service Fee $29.00 "
        "Total $29.61 Bell Payment History Paid 18/04/2026 09:36:20 - EFTPOS Owing"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="invoice", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].description == "Awanui Labs - Creatinine"


def test_parser_low_text_and_ocr_findings_are_carried_as_input_quality_warnings():
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


def test_parser_weak_ocr_quality_is_carried_as_input_quality_warning():
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
    assert result.transaction_candidates[0].amount == 94.25
    assert result.transaction_candidates[0].currency == "NZD"
    assert result.transaction_candidates[0].direction == "debit"
    assert fields["receipt_total"].normalized_value == "94.25"
    assert fields["gst_amount"].normalized_value == "12.29"
    assert fields["purchase_amount"].normalized_value == "94.25"
    assert fields["purchase_amount"].currency == "NZD"


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
    assert result.transaction_candidates[0].amount == 227.00
    assert result.transaction_candidates[0].currency == "NZD"
    assert result.transaction_candidates[0].direction == "debit"
    assert fields["card_receipt_amount"].normalized_value == "227.00"
    assert fields["card_receipt_amount"].currency == "NZD"


def test_receipt_total_transaction_uses_document_level_ocr_date():
    text = (
        "TAIPING ASIAN SUPERMARKET GST receipt yte: 28/05; "
        "Bean Longkou Vermicelli $2.49 including GST "
        "TERMINAL 998528 May 26 13:36 SWIFECARD "
        "REFERENCE 229245PUR CHASE NZD21. 96TOTAL"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 21.96
    assert result.transaction_candidates[0].date_text == "28/05/2026"


def test_receipt_ocr_damaged_card_amount_is_reviewable_transaction():
    text = (
        "HOP Puhinui fERMINAL 13 Aug 25 13:16 EF TPO CARD "
        "TOTAL NZDS5 GO APPROVED Customer receipt Date lime 1H/G8/2025 13.16.36 "
        "Due amount $ 56.00 flank Card § 55.00 Payment iD C8 2028-08-13"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 55.00
    assert result.transaction_candidates[0].currency == "NZD"
    assert result.transaction_candidates[0].date_text == "13/08/2025"
    assert "RECEIPT_PAYMENT_AMOUNT_REPAIRED" in result.transaction_candidates[0].reason_codes


def test_receipt_ocr_damaged_total_beats_item_like_sale_amount():
    text = (
        "HOP Puhinui * EFTPOS * TERMINAL 0002 13 Aug 25 13:16 CHEQUE "
        "EFTPOS ICI CONTACT CARD ************7414 RRN 001364865765 "
        "COMPLETE NZD55 . OF TOTAL NZ055 00 APPROVED CUSTOMER COPY "
        "Customer receipt Station name Puhinui Date Time 13/08/2025 13.16.36 "
        "Unregistered HOP iioney Sale 3 $5.00 Hue amount: , $ 56.00 flank Cara ) 85.00"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 55.00
    assert result.transaction_candidates[0].currency == "NZD"
    assert result.transaction_candidates[0].date_text == "13/08/2025"
    assert "RECEIPT_DAMAGED_TOTAL_REPAIRED" in result.transaction_candidates[0].reason_codes


def test_receipt_total_precedence_ignores_gst_amount_when_total_is_present():
    text = (
        "Receipt Store Sun 31/08/2025 03:01:41 SELF CHECKOUT TAX INVOICE "
        "Item Switch $25.54 @ Subfotal: $25.54 Total B25 .544 "
        "GST INCLUDED IN THE TOTAL $3.59 EFT CARD Change $0.00"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    fields = [field for field in result.financial_field_candidates if field.field_name == "receipt_total"]

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 25.54
    assert result.transaction_candidates[0].date_text == "31/08/2025"
    assert any(field.normalized_value == "25.54" and "RECEIPT_TOTAL_PRECEDENCE" in field.reason_codes for field in fields)


def test_receipt_description_prefers_sale_and_location_over_terminal_noise():
    text = (
        "HOP Puhinui fERMINAL 13 Aug 25 13:16 EF TPO CARD RRN 004564865 "
        "REFERENCE 029706 COMPLETE NZD55.00 APPROVED Customer receipt "
        "Station nane Puhinui Date lime 13/08/2025 13.16.36 "
        "ied 728 Unregistered HOP iioney Sale $ 55.00 flank Card § 55.00"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].description == "Unregistered HOP money Sale - Puhinui"
    assert "RRN" not in result.transaction_candidates[0].description
    assert "fERMINAL" not in result.transaction_candidates[0].description


def test_unknown_receipt_like_ocr_derives_receipt_total_transaction():
    text = (
        "Tax Invoice GST 123-456-789 "
        "Order 801 Retail Counter 1x Meal $15.80 Total due(GST inc): $30.60 "
        "Tax(GST): $3.99 Date:2026-05-31 11:42:14 Invoice Number 3201260531002"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="unknown", text=text))

    fields = {field.field_name: field for field in result.financial_field_candidates}

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 30.60
    assert result.transaction_candidates[0].direction == "debit"
    assert "OCR_RECEIPT_TOTAL_FALLBACK" in result.transaction_candidates[0].reason_codes
    assert fields["receipt_total"].normalized_value == "30.60"


def test_statement_shape_suppresses_receipt_total_fallback_when_misclassified_upstream():
    text = (
        "Credit Cards Statement of Account STATEMENT DATE NOVEMBER 07, 2023 "
        "PAYMENT DUE DATE NOVEMBER 28, 2023 CREDIT LIMIT 989,000.00 "
        "PREVIOUS BALANCE 77,803.97 TOTAL AMOUNT DUE 46,320.12 "
        "MINIMUM AMOUNT DUE 1,612.08 total purchase payment card"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 0
    assert result.evaluation.finding_counts["STATEMENT_SHAPE_RECEIPT_FALLBACK_SUPPRESSED"] == 1
    assert result.evaluation.finding_counts["NO_TRANSACTION_CANDIDATES"] == 1
    assert all("OCR_RECEIPT_TOTAL_FALLBACK" not in candidate.reason_codes for candidate in result.transaction_candidates)


def test_single_statement_term_does_not_suppress_receipt_total_fallback():
    text = "Tax Invoice Payment Due Date TOTAL 30.60 EFTPOS APPROVED"

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status == "completed"
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 30.60
    assert "STATEMENT_SHAPE_RECEIPT_FALLBACK_SUPPRESSED" not in result.evaluation.finding_counts


def test_payment_due_date_field_ignores_amount_only_noise():
    text = "Payment Due Date 4,088.74\nPayment Due Date 03 Jul 2019"

    result = extract_transactions(TransactionExtractionRequest(document_type="statement", text=text))

    due_dates = [field.normalized_value for field in result.financial_field_candidates if field.field_name == "payment_due_date"]
    assert "03 Jul 2019" in due_dates
    assert "4088.74" not in due_dates


def test_malformed_ocr_amount_token_returns_controlled_finding():
    text = "Tax Invoice GST APPROVED TOTAL: 3.225.00 EFTPOS complete"

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 0
    assert result.evaluation.finding_counts["MALFORMED_AMOUNT_TOKEN"] == 1
    assert result.evaluation.finding_counts["NO_TRANSACTION_CANDIDATES"] == 1


def test_malformed_layout_amount_token_returns_controlled_finding():
    rows = [
        "Statement From 13 MAY 2019 to 12 JUN 2019",
        "Previous Statement Balance 3,225.00",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "13 Jun 13 Jun OCR Damaged Amount 3.225.00",
    ]
    text = "\n".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
            text=text,
            pages=[{"page_number": 1, "text": text, "ocr_word_blocks": _word_blocks_from_rows(rows)}],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.evaluation.finding_counts["MALFORMED_AMOUNT_TOKEN"] == 1


def test_malformed_amount_token_does_not_warn_when_valid_transaction_extracted():
    text = "Store receipt TOTAL 30.60 note damaged OCR token 3.225.00"

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.summary.transaction_candidate_count == 1
    assert "MALFORMED_AMOUNT_TOKEN" not in result.evaluation.finding_counts


def test_unknown_receipt_photo_text_repairs_labelled_total_and_eftpos_amount():
    text = (
        "Tax Invoice MT Roskill FRESH DATE: 08-06-2026 12:19 "
        "LOTTE CHOCO PIE 168G 1 @ $3.49 $3.49 "
        "TOTAL:\n$34.33\nEFTPOS:\n$34.33\nINCLUDE TAX:\n$4.48"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="unknown", text=text))

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 34.33
    assert result.transaction_candidates[0].date_text == "08-06-2026"
    assert result.transaction_candidates[0].direction == "debit"
    assert result.transaction_candidates[0].reason_codes[0] in {
        "RECEIPT_EFTPOS_TOTAL_REPAIRED",
        "RECEIPT_LABELLED_TOTAL_REPAIRED",
    }


def test_receipt_split_decimal_total_beats_conflicting_eftpos_ocr():
    text = (
        "Tax Invoice MT Roskill FRESH DATE: 08-06-2026 12:19 "
        "LOTTE CHOCO PIE 168G 1 @ $3.49 $3.49 "
        "CHINESE HARD TOFU 2PCS 1 @ $4.49 $4.49 weight Meat 1 @ $10.87 $10.87 "
        "TOTAL: $34 33 EFTPOS: 48 94 INCLUDE TAX:"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="receipt", text=text))

    assert result.status in {"completed", "completed_with_warnings"}
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 34.33
    assert result.transaction_candidates[0].date_text == "08-06-2026"
    assert result.transaction_candidates[0].reason_codes[0] == "RECEIPT_DAMAGED_TOTAL_REPAIRED"


def test_single_line_medical_invoice_derives_paid_transaction_from_item_total():
    text = (
        "Invoice Example Labs Issued: 18/04/2026 09:36:20 "
        "Tax Invoice no.: 384590 Patient Name Example "
        "CC CRE - Creatinine $25.00 DRW - Service Fee $29.00 "
        "GLY - Glycated Haemoglobin $60.50 LIP - Lipid Tests $59.00 "
        "MAL - Albumin Creatinine Ratio $53.50 Total GST $29.61 "
        "Payment History Paid 18/04/2026 09:36:20 - EFTPOS Owing"
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="invoice",
            text=text,
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.transaction_candidate_count == 1
    assert result.transaction_candidates[0].amount == 227.00
    assert result.transaction_candidates[0].currency == "NZD"
    assert result.transaction_candidates[0].direction == "debit"
    assert "INVOICE_LINE_ITEM_TOTAL_DERIVED" in result.transaction_candidates[0].reason_codes
    fields = {field.field_name: field for field in result.financial_field_candidates}
    assert fields["total_gst"].currency == "NZD"


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


def test_transaction_classification_labels_transfer_for_m8():
    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="payment_proof",
            text="2026-01-08 Transfer to ACQUA EDEN RE PHP 17,274.97 Confirmation No. ABC123",
        )
    )

    candidate = result.transaction_candidates[0]

    assert candidate.transaction_type == "transfer"
    assert candidate.transaction_subtype == "bank_transfer"
    assert candidate.spending_category == "transfers"
    assert candidate.spending_subcategory == "bank_transfer"
    assert candidate.classification_source == "rules"
    assert "BANK_TRANSFER_SIGNALS" in candidate.transaction_type_reason_codes


def test_transaction_classification_labels_medical_spending_category_for_reports():
    text = (
        "Invoice Example Labs Issued: 18/04/2026 09:36:20 "
        "Tax Invoice no.: 384590 Patient Name Example "
        "CC CRE - Creatinine $25.00 DRW - Service Fee $29.00 "
        "Total GST $29.61 Payment History Paid 18/04/2026 09:36:20 - EFTPOS Owing"
    )

    result = extract_transactions(TransactionExtractionRequest(document_type="invoice", text=text))
    candidate = result.transaction_candidates[0]

    assert candidate.transaction_type in {"payment", "purchase"}
    assert candidate.spending_category == "medical"
    assert candidate.spending_subcategory == "diagnostics"
    assert candidate.spending_category_status == "classified"


def test_strong_rule_transaction_classification_skips_ai(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    calls = []
    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 0.50)
    monkeypatch.setitem(
        classifier_globals,
        "ai_classify_transaction",
        lambda **kwargs: calls.append(kwargs),
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="payment_proof",
            text="2026-01-08 Transfer to ACQUA EDEN RE PHP 17,274.97 Confirmation No. ABC123",
        )
    )

    assert calls == []
    assert result.transaction_candidates[0].classification_source == "rules"


def test_ai_enabled_but_settings_unavailable_reports_explicit_skip(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setitem(classifier_globals, "_load_active_settings", lambda: None)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 POS Merchant counter total PHP 34.33",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.classification_source == "ai_skipped_settings_unavailable"
    assert "AI_SKIPPED_SETTINGS_UNAVAILABLE" in candidate.classification_review_reason_codes
    assert "RECOGNITION_SETTINGS_UNAVAILABLE" in candidate.classification_review_reason_codes


def test_ai_enabled_but_api_key_missing_reports_explicit_skip(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_provider", "gemini")
    monkeypatch.setattr(settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "transaction_classification_ai_api_key_env", "MISSING_TEST_GEMINI_API_KEY")
    monkeypatch.delenv("MISSING_TEST_GEMINI_API_KEY", raising=False)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 POS Merchant counter total PHP 34.33",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.classification_source == "ai_skipped_api_key_missing"
    assert "AI_SKIPPED_API_KEY_MISSING" in candidate.classification_review_reason_codes


def test_ai_provider_failure_reports_explicit_skip(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_provider", "gemini")
    monkeypatch.setattr(settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "transaction_classification_ai_api_key_env", "TEST_GEMINI_API_KEY")
    monkeypatch.setenv("TEST_GEMINI_API_KEY", "configured-for-test")
    monkeypatch.setitem(classifier_globals, "ai_classify_transaction", lambda **kwargs: None)
    monkeypatch.setitem(classifier_globals, "ai_classification_failure_reason", lambda: "AI_SKIPPED_PROVIDER_CALL_FAILED")

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 POS Merchant counter total PHP 34.33",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.classification_source == "ai_skipped_provider_call_failed"
    assert "AI_SKIPPED_PROVIDER_CALL_FAILED" in candidate.classification_review_reason_codes


def test_weak_transaction_classification_accepts_ai_assist(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 0.70)
    monkeypatch.setattr(settings, "transaction_classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "transaction_classification_ai_model_version", "gemini-2.5-flash")
    monkeypatch.setitem(
        classifier_globals,
        "ai_classify_transaction",
        lambda **kwargs: {
            "transaction_type": "purchase",
            "transaction_subtype": "merchant_purchase",
            "spending_category": "shopping",
            "spending_subcategory": "retail",
            "confidence": 0.88,
            "reason_codes": ["AI_MERCHANT_PURCHASE"],
            "requires_review": False,
            "review_reason_codes": [],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        },
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 POS Merchant counter total PHP 34.33",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.transaction_type == "purchase"
    assert candidate.spending_category == "shopping"
    assert candidate.classification_source == "ai_assist"
    assert candidate.ai_confidence == 0.88
    assert "AI_ASSISTED_TRANSACTION_CLASSIFICATION" in candidate.transaction_type_reason_codes


def test_hsbc_debit_merchant_rows_do_not_use_generic_credit_context_as_refund(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    calls = []
    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 0.70)
    monkeypatch.setattr(settings, "transaction_classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "transaction_classification_ai_model_version", "gemini-2.5-flash")

    def fake_ai(**kwargs):
        calls.append(kwargs)
        return {
            "transaction_type": "purchase",
            "transaction_subtype": "merchant_purchase",
            "spending_category": "shopping",
            "spending_subcategory": "retail",
            "confidence": 0.88,
            "reason_codes": ["AI_MERCHANT_PURCHASE"],
            "requires_review": False,
            "review_reason_codes": [],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        }

    monkeypatch.setitem(classifier_globals, "ai_classify_transaction", fake_ai)

    rows = [
        "Statement From 13 AUG 2018 to 12 SEP 2018",
        "Previous Statement Balance 16,165.00",
        "Payments & Credits 16,165.00CR",
        "Purchases & Debits 7,155.00",
        "Total Due 7,155.00",
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP)",
        "11 Sep 09 Sep my LEWIN SMAURA = TAGUIG 1,990.00",
        "12 Sep 12 Sep Pelibesteeahbahaanaa 6 TH 5,165.00",
    ]
    text = "\n".join(rows)

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="statement",
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

    assert len(calls) == 2
    assert {candidate.transaction_type for candidate in result.transaction_candidates} == {"purchase"}
    assert all(candidate.transaction_subtype == "merchant_purchase" for candidate in result.transaction_candidates)
    assert all(candidate.classification_source == "ai_assist" for candidate in result.transaction_candidates)
    assert all("REFUND_REVERSAL_SIGNALS" not in candidate.transaction_type_reason_codes for candidate in result.transaction_candidates)


def test_ai_outside_active_vocabulary_becomes_pending_suggestion(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 0.70)
    monkeypatch.setattr(settings, "transaction_classification_ai_min_confidence", 0.76)
    monkeypatch.setattr(settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "transaction_classification_ai_model_version", "gemini-2.5-flash")
    monkeypatch.setitem(
        classifier_globals,
        "ai_classify_transaction",
        lambda **kwargs: {
            "transaction_type": "membership_topup",
            "transaction_subtype": "transport_card_topup",
            "spending_category": "public_transport",
            "spending_subcategory": "stored_value_topup",
            "confidence": 0.91,
            "reason_codes": ["AI_PUBLIC_TRANSPORT_TOPUP"],
            "requires_review": False,
            "review_reason_codes": [],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        },
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 HOP card topup customer receipt NZD 55.00",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.transaction_type == "membership_topup"
    assert candidate.spending_category == "public_transport"
    assert candidate.recognition_suggestion_status == "outside_vocabulary"
    assert candidate.recognition_suggestion_id.startswith("suggestion_")
    assert candidate.suggested_transaction_type == "membership_topup"
    assert candidate.suggested_spending_category == "public_transport"
    assert candidate.suggestion_source == "ai"
    assert candidate.classification_vocabulary_status == "outside_vocabulary_proposal"
    assert candidate.classification_confirmation_mode == "transaction_review_save"
    assert "AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED" in candidate.classification_review_reason_codes
    assert "AI_RECOGNITION_LABEL_SUGGESTION" in candidate.suggestion_reason_codes


def test_low_confidence_transaction_ai_result_is_rejected_for_review(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 0.70)
    monkeypatch.setattr(settings, "transaction_classification_ai_min_confidence", 0.76)
    monkeypatch.setitem(
        classifier_globals,
        "ai_classify_transaction",
        lambda **kwargs: {
            "transaction_type": "purchase",
            "transaction_subtype": "merchant_purchase",
            "spending_category": "shopping",
            "spending_subcategory": "retail",
            "confidence": 0.51,
            "reason_codes": ["AI_WEAK_SIGNAL"],
            "requires_review": True,
            "review_reason_codes": ["AI_CLASSIFICATION_REVIEW_REQUIRED"],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        },
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="receipt",
            text="2026-06-08 POS Merchant counter total PHP 34.33",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.classification_source == "rules_ai_low_confidence"
    assert candidate.transaction_type == "purchase"
    assert candidate.classification_review_required is True
    assert "AI_CONFIDENCE_BELOW_THRESHOLD" in candidate.classification_review_reason_codes


def test_conflicting_transaction_ai_result_preserves_rules_for_review(monkeypatch):
    classifier_globals = extract_transactions.__globals__["classify_transaction_candidate"].__globals__
    settings = classifier_globals["settings"]

    monkeypatch.setattr(settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(settings, "transaction_classification_ai_trigger_threshold", 1.01)
    monkeypatch.setattr(settings, "transaction_classification_ai_min_confidence", 0.76)
    monkeypatch.setitem(
        classifier_globals,
        "ai_classify_transaction",
        lambda **kwargs: {
            "transaction_type": "refund",
            "transaction_subtype": "merchant_refund",
            "spending_category": "income",
            "spending_subcategory": "refund_income",
            "confidence": 0.9,
            "reason_codes": ["AI_REFUND_SIGNAL"],
            "requires_review": True,
            "review_reason_codes": ["RULE_AI_TRANSACTION_TYPE_CONFLICT"],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        },
    )

    result = extract_transactions(
        TransactionExtractionRequest(
            document_type="payment_proof",
            text="2026-01-08 Transfer to ACQUA EDEN RE PHP 17,274.97 Confirmation No. ABC123",
        )
    )
    candidate = result.transaction_candidates[0]

    assert candidate.transaction_type == "transfer"
    assert candidate.spending_category == "transfers"
    assert candidate.classification_source == "rules_ai_conflict"
    assert candidate.classification_review_required is True
    assert "RULE_AI_TRANSACTION_TYPE_CONFLICT" in candidate.classification_review_reason_codes
