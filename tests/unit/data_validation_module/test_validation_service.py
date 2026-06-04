"""M8 - Data Validation Module Start
Verifies transaction data validation behavior.
M8 End"""

import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "data-validation-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
module_root_path = str(MODULE_ROOT)
if module_root_path in sys.path:
    sys.path.remove(module_root_path)
sys.path.insert(0, module_root_path)

from app.models.validation import DataValidationRequest
from app.services.validation_service import validate_data


def test_valid_m7_candidates_are_normalized(m7_candidates):
    m7_candidates["transaction_candidates"][0]["posted_date_text"] = "Nov 03 2023"

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed"
    assert result.summary.normalized_record_count == 2
    assert result.summary.valid_record_count == 2
    assert result.normalized_records[0].transaction_date == "2023-11-02"
    assert result.normalized_records[0].posted_date == "2023-11-03"
    assert result.normalized_records[1].signed_amount == -2345.67
    assert result.financial_fields[0].value == "46320.12"


def test_missing_date_unknown_direction_and_low_confidence_return_warnings():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                {
                    "candidate_id": "txn_warn",
                    "date_text": None,
                    "description": "Transfer to Vendor",
                    "amount": 100.0,
                    "currency": "PHP",
                    "direction": "unknown",
                    "confidence": 0.44,
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.warning_record_count == 1
    assert result.evaluation.finding_counts["MISSING_TRANSACTION_DATE"] == 1
    assert result.evaluation.finding_counts["UNKNOWN_DIRECTION"] == 1
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_RECORD"] == 1


def test_invalid_amount_and_blank_description_mark_record_invalid():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                {
                    "candidate_id": "txn_bad",
                    "date_text": "2026-01-08",
                    "description": "   ",
                    "amount": 0,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.91,
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.invalid_record_count == 1
    assert result.evaluation.finding_counts["INVALID_AMOUNT"] == 1
    assert result.evaluation.finding_counts["MISSING_DESCRIPTION"] == 1


def test_duplicate_transactions_are_marked(m7_candidates):
    duplicate = dict(m7_candidates["transaction_candidates"][1])
    duplicate["candidate_id"] = "txn_0003"
    duplicate["description"] = "purchase   general store"
    m7_candidates["transaction_candidates"].append(duplicate)

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed_with_warnings"
    assert result.summary.duplicate_record_count == 1
    assert result.normalized_records[2].duplicate_of == "record_txn_0002"
    assert result.evaluation.finding_counts["DUPLICATE_TRANSACTION"] == 1


def test_duplicate_detection_can_be_disabled(m7_candidates):
    duplicate = dict(m7_candidates["transaction_candidates"][1])
    duplicate["candidate_id"] = "txn_0003"
    m7_candidates["transaction_candidates"].append(duplicate)
    m7_candidates["options"] = {"enable_duplicate_detection": False}

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed"
    assert result.summary.duplicate_record_count == 0


def test_financial_field_low_confidence_is_marked_warning():
    result = validate_data(
        DataValidationRequest(
            document_type="invoice",
            financial_field_candidates=[
                {
                    "field_name": "total_amount_due",
                    "value_text": "99.00",
                    "normalized_value": "99.00",
                    "currency": "PHP",
                    "confidence": 0.4,
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.financial_fields[0].quality_status == "warning"
    assert "LOW_CONFIDENCE_FIELD" in result.financial_fields[0].reason_codes
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_FIELD"] == 1


def test_richer_m7_candidate_groups_are_preserved_and_summarized(m7_candidates):
    m7_candidates["section_candidates"] = [
        {
            "section_id": "section_1_statement_summary",
            "section_label": "statement_summary",
            "page_number": 1,
            "first_line_number": 1,
            "last_line_number": 4,
            "source_text_redacted": "TOTAL AMOUNT DUE 46,320.12",
            "confidence": 0.82,
            "reason_codes": ["SECTION_KEYWORD_DETECTED"],
        }
    ]
    m7_candidates["financial_field_candidates"][0]["field_label"] = "TOTAL AMOUNT DUE"
    m7_candidates["financial_field_candidates"][0]["value_type"] = "amount"
    m7_candidates["financial_field_candidates"][0]["source"]["section_label"] = "statement_summary"
    m7_candidates["financial_field_candidates"][0]["source"]["section_id"] = "section_1_statement_summary"
    m7_candidates["entity_candidates"] = [
        {
            "entity_id": "entity_0001",
            "entity_type": "institution_name",
            "value_text": "Example Bank",
            "normalized_value": "Example Bank",
            "confidence": 0.8,
        }
    ]
    m7_candidates["reference_candidates"] = [
        {
            "reference_id": "ref_0001",
            "reference_type": "confirmation_number",
            "value_text": "32110001",
            "normalized_value": "****0001",
            "masked": True,
            "confidence": 0.86,
        }
    ]
    m7_candidates["line_item_candidates"] = [
        {
            "line_item_id": "item_0001",
            "description": "Service fee",
            "amount": 25.0,
            "currency": "PHP",
            "confidence": 0.75,
        }
    ]

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed"
    assert result.summary.section_candidate_count == 1
    assert result.summary.entity_count == 1
    assert result.summary.reference_count == 1
    assert result.summary.line_item_count == 1
    assert result.financial_fields[0].field_label == "TOTAL AMOUNT DUE"
    assert result.document_financial_summary["total_amount_due"] == "46320.12"
    assert result.validated_references[0].value == "****0001"


def test_installment_candidate_creates_review_item_without_changing_transaction_totals(m7_candidates):
    m7_candidates["installment_candidates"] = [
        {
            "installment_id": "installment_0001",
            "purchase_date_text": "November 21 2019",
            "posted_date_text": "November 25 2019",
            "description": "Electronics Store Megamall",
            "principal_amount": 31998.00,
            "currency": "PHP",
            "confidence": 0.86,
            "reason_codes": ["INSTALLMENT_PURCHASE_PRINCIPAL"],
            "source": {
                "page_number": 1,
                "line_number": 50,
                "text": "November 21 November 25 Electronics Store Megamall 31,998.00",
                "section_label": "installment_balances",
            },
        }
    ]

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.summary.installment_count == 1
    assert result.summary.warning_installment_count == 1
    assert result.summary.debit_total == 2345.67
    assert result.normalized_installments[0].principal_amount == 31998.00
    assert result.normalized_installments[0].quality_status == "warning"
    assert "MISSING_INSTALLMENT_TERM" in result.normalized_installments[0].reason_codes
    assert result.review_items[-1].item_type == "installment"
    assert result.review_items[-1].record_id == result.normalized_installments[0].installment_id
    assert "MISSING_INSTALLMENT_TERM" in result.review_items[-1].reason_codes
    assert result.review_items[-1].title == "Check installment term"


def test_low_confidence_entities_and_references_use_specific_warning_codes():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            entity_candidates=[
                {
                    "entity_id": "entity_low",
                    "entity_type": "merchant_name",
                    "value_text": "Example Merchant",
                    "normalized_value": "Example Merchant",
                    "confidence": 0.4,
                }
            ],
            reference_candidates=[
                {
                    "reference_id": "ref_low",
                    "reference_type": "approval_code",
                    "value_text": "ABC123",
                    "normalized_value": "ABC123",
                    "masked": True,
                    "confidence": 0.4,
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.validated_entities[0].quality_status == "warning"
    assert result.validated_references[0].quality_status == "warning"
    assert "LOW_CONFIDENCE_ENTITY" in result.validated_entities[0].reason_codes
    assert "LOW_CONFIDENCE_REFERENCE" in result.validated_references[0].reason_codes
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_ENTITY"] == 1
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_REFERENCE"] == 1
    assert "LOW_CONFIDENCE_FIELD" not in result.evaluation.finding_counts


def test_document_financial_summary_excludes_transaction_table_fields(m7_candidates):
    m7_candidates["financial_field_candidates"].append(
        {
            "field_name": "purchase_amount",
            "field_label": "PURCHASE",
            "value_type": "amount",
            "value_text": "2,345.67",
            "normalized_value": "2345.67",
            "currency": "PHP",
            "source": {
                "page_number": 1,
                "line_number": 6,
                "text": "Nov 05 2023 Purchase General Store 2,345.67",
                "section_label": "transaction_table",
            },
            "confidence": 0.86,
            "reason_codes": ["FIELD_LABEL_DETECTED", "AMOUNT_DETECTED"],
        }
    )

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert "total_amount_due" in result.document_financial_summary
    assert "purchase_amount" not in result.document_financial_summary


def test_transaction_candidate_from_non_transaction_section_needs_review(m7_candidates):
    m7_candidates["transaction_candidates"] = [
        {
            "candidate_id": "txn_summary",
            "date_text": "Nov 07 2023",
            "description": "Credit limit",
            "amount": 989000.0,
            "currency": "PHP",
            "direction": "credit",
            "source": {
                "page_number": 1,
                "line_number": 8,
                "text": "CREDIT LIMIT 989,000.00",
                "section_label": "statement_summary",
            },
            "confidence": 0.9,
            "reason_codes": ["AMOUNT_DETECTED"],
        }
    ]
    m7_candidates["financial_field_candidates"] = []

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed_with_warnings"
    assert result.summary.warning_record_count == 1
    assert result.normalized_records[0].quality_status == "warning"
    assert "NON_TRANSACTION_SECTION" in result.normalized_records[0].reason_codes
    assert result.evaluation.finding_counts["NON_TRANSACTION_SECTION"] == 1


def test_repaired_ocr_candidate_creates_guided_review_item():
    result = validate_data(
        DataValidationRequest(
            document_type="statement",
            transaction_candidates=[
                {
                    "candidate_id": "txn_ocr",
                    "date_text": "22 Nov 2023",
                    "posted_date_text": "19 Nov 2023",
                    "description": "IANG NAN FOOD MAKATI",
                    "amount": 2935.80,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.9,
                    "reason_codes": ["OCR_LAYOUT_REPAIRED", "DESCRIPTION_PREFIX_REPAIRED"],
                    "source": {
                        "page_number": 3,
                        "line_number": 132,
                        "text": "IANG NAN FOOD MAKATI 22 Nov 19 Nov a H 2,935.80",
                        "section_label": "transaction_table",
                    },
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.review_item_count == 1
    assert result.summary.document_review_status == "needs_review"
    assert result.summary.recommended_action == "review_items"
    assert result.normalized_records[0].quality_status == "warning"
    assert "SUSPICIOUS_OCR_TEXT" in result.normalized_records[0].reason_codes
    assert result.review_items[0].title == "Check OCR text"
    assert result.evaluation.finding_counts["SUSPICIOUS_OCR_TEXT"] == 1


def test_iso_dates_still_normalize_and_legitimate_i_prefix_is_not_suspicious():
    result = validate_data(
        DataValidationRequest(
            document_type="statement",
            transaction_candidates=[
                {
                    "candidate_id": "txn_iso",
                    "date_text": "2023-11-22",
                    "posted_date_text": "2023-11-19",
                    "description": "IKEA MAKATI",
                    "amount": 2935.80,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.9,
                    "reason_codes": ["OCR_LAYOUT_REPAIRED"],
                    "source": {
                        "page_number": 3,
                        "line_number": 132,
                        "text": "IKEA MAKATI 2023-11-22 2023-11-19 2,935.80",
                        "section_label": "transaction_table",
                    },
                }
            ],
        )
    )

    assert result.normalized_records[0].transaction_date == "2023-11-22"
    assert result.normalized_records[0].posted_date == "2023-11-19"
    assert "SUSPICIOUS_OCR_TEXT" not in result.normalized_records[0].reason_codes
    assert "SUSPICIOUS_OCR_TEXT" not in result.evaluation.finding_counts


def test_low_confidence_ocr_amount_creates_guided_review_item_without_reconciliation():
    result = validate_data(
        DataValidationRequest(
            document_type="statement",
            transaction_candidates=[
                {
                    "candidate_id": "txn_low_amount",
                    "date_text": "07 Dec 2023",
                    "posted_date_text": "05 Dec 2023",
                    "description": "CONTIS BATANGAS CITY BATANGAS PH",
                    "amount": 457.79,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.9,
                    "reason_codes": ["OCR_LAYOUT_ROW_RECONSTRUCTED", "AMOUNT_DETECTED"],
                    "source": {
                        "page_number": 4,
                        "line_number": 151,
                        "text": "07 Dec 05 Dec CONTIS BATANGAS CITY BATANGAS PH 457.79",
                        "section_label": "transaction_table",
                        "ocr_confidence": 0.5,
                    },
                }
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.warning_record_count == 1
    assert result.summary.review_item_count == 1
    assert result.summary.document_review_status == "needs_review"
    assert result.normalized_records[0].quality_status == "warning"
    assert "LOW_CONFIDENCE_AMOUNT" in result.normalized_records[0].reason_codes
    assert result.review_items[0].title == "Check amount"
    assert result.review_items[0].recommended_action == "edit_or_accept"
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_AMOUNT"] == 1
    assert "DOCUMENT_RECONCILIATION_REVIEW" not in result.evaluation.finding_counts


def test_reconciliation_mismatch_creates_document_review_item(m7_candidates):
    m7_candidates["reconciliation"] = {
        "status": "needs_review",
        "previous_balance": 61586.10,
        "debit_total": 102478.16,
        "credit_total": 65286.10,
        "total_due": 100993.16,
        "computed_total_due": 98778.16,
        "difference": -2215.00,
        "reason_codes": ["STATEMENT_TOTAL_MISMATCH"],
    }

    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed_with_warnings"
    assert result.summary.review_item_count == 1
    assert result.summary.document_review_status == "needs_review"
    assert result.summary.reconciliation_delta == -2215.00
    assert result.review_items[0].item_type == "document_reconciliation"
    assert "DOCUMENT_RECONCILIATION_REVIEW" in result.review_items[0].reason_codes
    assert result.evaluation.finding_counts["DOCUMENT_RECONCILIATION_REVIEW"] == 1
