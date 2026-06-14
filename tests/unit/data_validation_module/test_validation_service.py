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


def _classified_candidate(**overrides):
    candidate = {
        "candidate_id": "txn_classified",
        "date_text": "2026-01-08",
        "description": "Classified transaction",
        "amount": 100.0,
        "currency": "PHP",
        "direction": "debit",
        "confidence": 0.9,
        "transaction_type": "purchase",
        "transaction_subtype": "merchant_purchase",
        "transaction_type_confidence": 0.86,
        "transaction_type_status": "classified",
        "transaction_type_reason_codes": ["MERCHANT_PURCHASE_SIGNALS"],
        "spending_category": "shopping",
        "spending_subcategory": "retail",
        "spending_category_confidence": 0.84,
        "spending_category_status": "classified",
        "spending_category_reason_codes": ["RETAIL_CATEGORY_SIGNALS"],
        "classification_source": "rules",
    }
    candidate.update(overrides)
    return candidate


def test_valid_extraction_candidates_are_normalized(extraction_candidates):
    extraction_candidates["transaction_candidates"][0]["posted_date_text"] = "Nov 03 2023"

    result = validate_data(DataValidationRequest(**extraction_candidates))

    assert result.status == "completed"
    assert result.summary.normalized_record_count == 2
    assert result.summary.valid_record_count == 2
    assert result.normalized_records[0].transaction_date == "2023-11-02"
    assert result.normalized_records[0].posted_date == "2023-11-03"
    assert result.normalized_records[1].signed_amount == -2345.67
    assert result.financial_fields[0].value == "46320.12"


def test_hyphenated_receipt_date_is_normalized():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                _classified_candidate(**{
                    "candidate_id": "txn_receipt",
                    "date_text": "24-05-2026",
                    "description": "Receipt purchase",
                    "amount": 56.0,
                    "currency": "NZD",
                    "direction": "debit",
                    "source": {"page_number": 1, "line_number": 1, "text": "DATE: 24-05-2026 TOTAL $56.00"},
                    "confidence": 0.82,
                    "reason_codes": ["RECEIPT_TOTAL_TRANSACTION_DERIVED", "AMOUNT_DETECTED"],
                })
            ],
        )
    )

    assert result.normalized_records[0].transaction_date == "2026-05-24"
    assert "MISSING_TRANSACTION_DATE" not in result.normalized_records[0].reason_codes


def test_missing_date_unknown_direction_and_low_confidence_return_warnings():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                _classified_candidate(**{
                    "candidate_id": "txn_warn",
                    "date_text": None,
                    "description": "Transfer to Vendor",
                    "amount": 100.0,
                    "currency": "PHP",
                    "direction": "unknown",
                    "confidence": 0.44,
                })
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.warning_record_count == 1
    assert result.evaluation.finding_counts["MISSING_TRANSACTION_DATE"] == 1
    assert result.evaluation.finding_counts["UNKNOWN_DIRECTION"] == 1
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_RECORD"] == 1


def test_pending_recognition_suggestion_is_preserved_and_marked_for_review():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                _classified_candidate(**{
                    "candidate_id": "txn_suggested_label",
                    "recognition_suggestion_id": "suggestion_123",
                    "recognition_suggestion_status": "pending",
                    "suggested_transaction_type": "transport",
                    "suggested_transaction_subtype": "public_transport_topup",
                    "suggested_spending_category": "transport",
                    "suggested_spending_subcategory": "stored_value_card",
                    "suggestion_confidence": 0.81,
                    "suggestion_reason_codes": ["AI_LABEL_SUGGESTION"],
                    "suggestion_source": "ai",
                    "suggestion_evidence_ref": "redacted:evidence:1",
                })
            ],
        )
    )

    record = result.normalized_records[0]
    assert result.status == "completed_with_warnings"
    assert record.recognition_suggestion_id == "suggestion_123"
    assert record.recognition_suggestion_status == "pending"
    assert record.suggested_transaction_type == "transport"
    assert record.suggested_spending_subcategory == "stored_value_card"
    assert record.suggestion_confidence == 0.81
    assert "PENDING_RECOGNITION_LABEL_SUGGESTION" in record.reason_codes
    assert result.evaluation.finding_counts["PENDING_RECOGNITION_LABEL_SUGGESTION"] == 1


def test_ai_outside_vocabulary_suggestion_requires_user_confirmation():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                _classified_candidate(**{
                    "candidate_id": "txn_ai_new_label",
                    "transaction_type": "membership_topup",
                    "transaction_subtype": "transport_card_topup",
                    "spending_category": "public_transport",
                    "spending_subcategory": "stored_value_topup",
                    "recognition_suggestion_id": "suggestion_ai_new",
                    "recognition_suggestion_status": "outside_vocabulary",
                    "suggested_transaction_type": "membership_topup",
                    "suggested_transaction_subtype": "transport_card_topup",
                    "suggested_spending_category": "public_transport",
                    "suggested_spending_subcategory": "stored_value_topup",
                    "suggestion_confidence": 0.91,
                    "suggestion_reason_codes": ["AI_RECOGNITION_LABEL_SUGGESTION"],
                    "suggestion_source": "ai",
                    "classification_vocabulary_status": "outside_vocabulary_proposal",
                    "classification_confirmation_mode": "transaction_review_save",
                    "classification_review_required": True,
                })
            ],
        )
    )

    record = result.normalized_records[0]

    assert record.classification_vocabulary_status == "outside_vocabulary_proposal"
    assert record.classification_confirmation_mode == "transaction_review_save"
    assert "AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED" in record.reason_codes
    assert result.evaluation.finding_counts["AI_CLASSIFICATION_USER_CONFIRMATION_REQUIRED"] == 1


def test_invalid_amount_and_blank_description_mark_record_invalid():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                _classified_candidate(**{
                    "candidate_id": "txn_bad",
                    "date_text": "2026-01-08",
                    "description": "   ",
                    "amount": 0,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.91,
                })
            ],
        )
    )

    assert result.status == "completed_with_warnings"
    assert result.summary.invalid_record_count == 1
    assert result.evaluation.finding_counts["INVALID_AMOUNT"] == 1
    assert result.evaluation.finding_counts["MISSING_DESCRIPTION"] == 1


def test_duplicate_transactions_are_marked(extraction_candidates):
    duplicate = dict(extraction_candidates["transaction_candidates"][1])
    duplicate["candidate_id"] = "txn_0003"
    duplicate["description"] = "purchase   general store"
    extraction_candidates["transaction_candidates"].append(duplicate)

    result = validate_data(DataValidationRequest(**extraction_candidates))

    assert result.status == "completed_with_warnings"
    assert result.summary.duplicate_record_count == 1
    assert result.normalized_records[2].duplicate_of == "record_txn_0002"
    assert result.evaluation.finding_counts["DUPLICATE_TRANSACTION"] == 1


def test_duplicate_detection_can_be_disabled(extraction_candidates):
    duplicate = dict(extraction_candidates["transaction_candidates"][1])
    duplicate["candidate_id"] = "txn_0003"
    extraction_candidates["transaction_candidates"].append(duplicate)
    extraction_candidates["options"] = {"enable_duplicate_detection": False}

    result = validate_data(DataValidationRequest(**extraction_candidates))

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


def test_richer_extraction_candidate_groups_are_preserved_and_summarized(extraction_candidates):
    extraction_candidates["section_candidates"] = [
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
    extraction_candidates["financial_field_candidates"][0]["field_label"] = "TOTAL AMOUNT DUE"
    extraction_candidates["financial_field_candidates"][0]["value_type"] = "amount"
    extraction_candidates["financial_field_candidates"][0]["source"]["section_label"] = "statement_summary"
    extraction_candidates["financial_field_candidates"][0]["source"]["section_id"] = "section_1_statement_summary"
    extraction_candidates["entity_candidates"] = [
        {
            "entity_id": "entity_0001",
            "entity_type": "institution_name",
            "value_text": "Example Bank",
            "normalized_value": "Example Bank",
            "confidence": 0.8,
        }
    ]
    extraction_candidates["reference_candidates"] = [
        {
            "reference_id": "ref_0001",
            "reference_type": "confirmation_number",
            "value_text": "32110001",
            "normalized_value": "****0001",
            "masked": True,
            "confidence": 0.86,
        }
    ]
    extraction_candidates["line_item_candidates"] = [
        {
            "line_item_id": "item_0001",
            "description": "Service fee",
            "amount": 25.0,
            "currency": "PHP",
            "confidence": 0.75,
        }
    ]

    result = validate_data(DataValidationRequest(**extraction_candidates))

    assert result.status == "completed"
    assert result.summary.section_candidate_count == 1
    assert result.summary.entity_count == 1
    assert result.summary.reference_count == 1
    assert result.summary.line_item_count == 1
    assert result.financial_fields[0].field_label == "TOTAL AMOUNT DUE"
    assert result.document_financial_summary["total_amount_due"] == "46320.12"
    assert result.validated_references[0].value == "****0001"


def test_installment_candidate_creates_review_item_without_changing_transaction_totals(extraction_candidates):
    extraction_candidates["installment_candidates"] = [
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

    result = validate_data(DataValidationRequest(**extraction_candidates))

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


def test_document_financial_summary_excludes_transaction_table_fields(extraction_candidates):
    extraction_candidates["financial_field_candidates"].append(
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

    result = validate_data(DataValidationRequest(**extraction_candidates))

    assert "total_amount_due" in result.document_financial_summary
    assert "purchase_amount" not in result.document_financial_summary


def test_transaction_candidate_from_non_transaction_section_needs_review(extraction_candidates):
    extraction_candidates["transaction_candidates"] = [
        _classified_candidate(**{
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
        })
    ]
    extraction_candidates["financial_field_candidates"] = []

    result = validate_data(DataValidationRequest(**extraction_candidates))

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
                _classified_candidate(**{
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
                })
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


def test_iso_dates_and_short_alphanumeric_merchants_are_not_suspicious():
    result = validate_data(
        DataValidationRequest(
            document_type="statement",
            transaction_candidates=[
                _classified_candidate(**{
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
                }),
                _classified_candidate(**{
                    "candidate_id": "txn_short_merchant",
                    "date_text": "22 Nov 2023",
                    "posted_date_text": "19 Nov 2023",
                    "description": "3M SUPPLIES MAKATI",
                    "amount": 1200.00,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.9,
                    "reason_codes": ["OCR_LAYOUT_REPAIRED"],
                    "source": {
                        "page_number": 3,
                        "line_number": 133,
                        "text": "3M SUPPLIES MAKATI 22 Nov 19 Nov 1,200.00",
                        "section_label": "transaction_table",
                    },
                })
            ],
        )
    )

    assert result.normalized_records[0].transaction_date == "2023-11-22"
    assert result.normalized_records[0].posted_date == "2023-11-19"
    assert "SUSPICIOUS_OCR_TEXT" not in result.normalized_records[0].reason_codes
    assert "SUSPICIOUS_OCR_TEXT" not in result.normalized_records[1].reason_codes
    assert "SUSPICIOUS_OCR_TEXT" not in result.evaluation.finding_counts


def test_low_confidence_ocr_amount_creates_guided_review_item_without_reconciliation():
    result = validate_data(
        DataValidationRequest(
            document_type="statement",
            transaction_candidates=[
                _classified_candidate(**{
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
                })
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


def test_reconciliation_mismatch_creates_document_review_item(extraction_candidates):
    extraction_candidates["reconciliation"] = {
        "status": "needs_review",
        "previous_balance": 61586.10,
        "debit_total": 102478.16,
        "credit_total": 65286.10,
        "total_due": 100993.16,
        "computed_total_due": 98778.16,
        "difference": -2215.00,
        "reason_codes": ["STATEMENT_TOTAL_MISMATCH"],
    }

    result = validate_data(DataValidationRequest(**extraction_candidates))

    assert result.status == "completed_with_warnings"
    assert result.summary.review_item_count == 1
    assert result.summary.document_review_status == "needs_review"
    assert result.summary.reconciliation_delta == -2215.00
    assert result.review_items[0].item_type == "document_reconciliation"
    assert "DOCUMENT_RECONCILIATION_REVIEW" in result.review_items[0].reason_codes
    assert result.evaluation.finding_counts["DOCUMENT_RECONCILIATION_REVIEW"] == 1


def test_transaction_classification_fields_are_preserved_for_reporting():
    result = validate_data(
        DataValidationRequest(
            document_type="payment_proof",
            transaction_candidates=[
                {
                    "candidate_id": "txn_transfer",
                    "date_text": "2026-01-08",
                    "description": "Transfer to Acqua Eden",
                    "amount": 17274.97,
                    "currency": "PHP",
                    "direction": "debit",
                    "confidence": 0.9,
                    "transaction_type": "transfer",
                    "transaction_subtype": "bank_transfer",
                    "transaction_type_confidence": 0.78,
                    "transaction_type_status": "classified",
                    "transaction_type_reason_codes": ["BANK_TRANSFER_SIGNALS"],
                    "transaction_type_scores": {"transfer.bank_transfer": 0.78},
                    "spending_category": "transfers",
                    "spending_subcategory": "bank_transfer",
                    "spending_category_confidence": 0.84,
                    "spending_category_status": "classified",
                    "spending_category_reason_codes": ["TRANSFER_CATEGORY_SIGNALS"],
                    "spending_category_scores": {"transfers.bank_transfer": 0.84},
                    "classification_source": "rules",
                    "ai_model_name": "gemini-2.5-flash",
                    "ai_model_version": "gemini-2.5-flash",
                    "ai_confidence": 0.84,
                }
            ],
        )
    )

    record = result.normalized_records[0]

    assert result.status == "completed"
    assert record.transaction_type == "transfer"
    assert record.transaction_subtype == "bank_transfer"
    assert record.spending_category == "transfers"
    assert record.spending_subcategory == "bank_transfer"
    assert record.classification_source == "rules"
    assert record.ai_model_name == "gemini-2.5-flash"
    assert record.ai_confidence == 0.84


def test_unknown_document_type_blocks_transaction_save():
    result = validate_data(
        DataValidationRequest(
            document_type="unknown",
            transaction_candidates=[_classified_candidate()],
        )
    )

    record = result.normalized_records[0]

    assert result.status == "completed_with_warnings"
    assert record.quality_status == "invalid"
    assert "UNKNOWN_DOCUMENT_TYPE" in record.reason_codes
    assert result.summary.valid_record_count == 0
    assert result.summary.invalid_record_count == 1
    assert result.summary.document_review_status == "blocked"
    assert result.evaluation.finding_counts["UNKNOWN_DOCUMENT_TYPE"] == 1


def test_low_confidence_required_classifications_create_review_item_without_blocking():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            document_type_confidence=0.42,
            document_type_status="classified",
            transaction_candidates=[
                _classified_candidate(
                    transaction_type_confidence=0.43,
                    spending_category_confidence=0.44,
                )
            ],
        )
    )

    record = result.normalized_records[0]

    assert result.status == "completed_with_warnings"
    assert record.quality_status == "warning"
    assert "LOW_CONFIDENCE_DOCUMENT_TYPE" in record.reason_codes
    assert "LOW_CONFIDENCE_TRANSACTION_TYPE" in record.reason_codes
    assert "LOW_CONFIDENCE_SPENDING_CATEGORY" in record.reason_codes
    assert result.summary.warning_record_count == 1
    assert result.summary.invalid_record_count == 0
    assert result.summary.document_review_status == "needs_review"
    assert result.evaluation.finding_counts["LOW_CONFIDENCE_DOCUMENT_TYPE"] == 1


def test_supplied_unknown_transaction_classification_creates_review_item():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                {
                    "candidate_id": "txn_unclear_category",
                    "date_text": "2026-06-08",
                    "description": "Blurred merchant receipt",
                    "amount": 34.33,
                    "currency": "NZD",
                    "direction": "debit",
                    "confidence": 0.82,
                    "transaction_type": "unknown",
                    "transaction_type_confidence": 0.2,
                    "transaction_type_status": "unknown",
                    "transaction_type_reason_codes": ["NO_CLASSIFICATION_SIGNALS"],
                    "spending_category": "uncategorized",
                    "spending_category_confidence": 0.2,
                    "spending_category_status": "unknown",
                    "spending_category_reason_codes": ["NO_CLASSIFICATION_SIGNALS"],
                    "classification_source": "rules",
                }
            ],
        )
    )

    record = result.normalized_records[0]

    assert result.status == "completed_with_warnings"
    assert record.quality_status == "warning"
    assert "UNKNOWN_TRANSACTION_TYPE" in record.reason_codes
    assert "UNKNOWN_SPENDING_CATEGORY" in record.reason_codes
    assert result.summary.warning_record_count == 1
    assert result.summary.invalid_record_count == 0
    assert result.summary.valid_record_count == 0
    assert result.summary.review_item_count == 1
    assert result.summary.document_review_status == "needs_review"
    assert result.evaluation.finding_counts["UNKNOWN_TRANSACTION_TYPE"] == 1
    assert result.evaluation.finding_counts["UNKNOWN_SPENDING_CATEGORY"] == 1


def test_ai_transaction_classification_review_metadata_creates_review_item():
    result = validate_data(
        DataValidationRequest(
            document_type="receipt",
            transaction_candidates=[
                {
                    "candidate_id": "txn_ai_conflict",
                    "date_text": "2026-06-08",
                    "description": "Transfer to Vendor",
                    "amount": 34.33,
                    "currency": "NZD",
                    "direction": "debit",
                    "confidence": 0.9,
                    "transaction_type": "transfer",
                    "transaction_subtype": "bank_transfer",
                    "transaction_type_confidence": 0.82,
                    "transaction_type_status": "classified",
                    "spending_category": "transfers",
                    "spending_subcategory": "bank_transfer",
                    "spending_category_confidence": 0.82,
                    "spending_category_status": "classified",
                    "classification_source": "rules_ai_conflict",
                    "ai_model_name": "gemini-2.5-flash",
                    "ai_model_version": "gemini-2.5-flash",
                    "ai_confidence": 0.91,
                    "classification_review_required": True,
                    "classification_review_reason_codes": ["RULE_AI_TRANSACTION_TYPE_CONFLICT"],
                }
            ],
        )
    )

    record = result.normalized_records[0]

    assert result.status == "completed_with_warnings"
    assert record.quality_status == "warning"
    assert record.classification_source == "rules_ai_conflict"
    assert record.classification_review_required is True
    assert "RULE_AI_TRANSACTION_TYPE_CONFLICT" in record.reason_codes
    assert result.summary.review_item_count == 1
    assert result.evaluation.finding_counts["AI_CLASSIFICATION_REVIEW_REQUIRED"] == 1


def test_document_recognition_suggestion_metadata_is_preserved_for_m9():
    result = validate_data(
        DataValidationRequest(
            document_type="unknown",
            document_type_status="unknown",
            document_recognition_suggestion_id="doc_suggestion_1",
            document_recognition_suggestion_status="pending",
            suggested_document_type="receipt",
            suggested_document_subtype="tax_receipt",
            document_suggestion_confidence=0.91,
            document_suggestion_reason_codes=["AI_SUGGESTED_INACTIVE_DOCUMENT_LABEL"],
            document_suggestion_source="m5_ai_document_classification",
            document_suggestion_evidence_ref="m5:redacted_classification_prompt",
            financial_field_candidates=[
                {
                    "field_name": "receipt_total",
                    "value_text": "34.33",
                    "normalized_value": "34.33",
                    "value_type": "amount",
                    "confidence": 0.9,
                }
            ],
        )
    )

    assert result.document_type == "unknown"
    assert result.document_recognition_suggestion_id == "doc_suggestion_1"
    assert result.document_recognition_suggestion_status == "pending"
    assert result.suggested_document_type == "receipt"
    assert result.suggested_document_subtype == "tax_receipt"
    assert result.document_suggestion_confidence == 0.91
    assert result.document_suggestion_source == "m5_ai_document_classification"
