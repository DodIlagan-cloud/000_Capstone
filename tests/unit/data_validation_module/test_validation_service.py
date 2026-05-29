"""M8 - Data Validation Module Start
Verifies transaction data validation behavior.
M8 End"""

from app.models.validation import DataValidationRequest
from app.services.validation_service import validate_data


def test_valid_m7_candidates_are_normalized(m7_candidates):
    result = validate_data(DataValidationRequest(**m7_candidates))

    assert result.status == "completed"
    assert result.summary.normalized_record_count == 2
    assert result.summary.valid_record_count == 2
    assert result.normalized_records[0].transaction_date == "2023-11-02"
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
    duplicate["description"] = "purchase   grocery store"
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
