"""M9 - Stats Data and Persistence Start
Tests validation result persistence using configured real test input.
M9 End"""

from __future__ import annotations

import mimetypes
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
STATS_DATA_SRC = REPO_ROOT / "apps" / "stats-data" / "src"
STATS_DATA_SCRIPTS = REPO_ROOT / "apps" / "stats-data" / "scripts"
if str(STATS_DATA_SRC) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SRC))
if str(STATS_DATA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STATS_DATA_SCRIPTS))

from stats_data.validation_persistence import (  # noqa: E402
    SPENDING_SUBCATEGORY_PARENT_MAP,
    TRANSACTION_SUBTYPE_PARENT_MAP,
    _activate_confirmed_classifications,
    _classification_activation_allowed,
    _execute_insert_if_missing,
    _mark_promoted,
    build_validation_persistence_plan,
    build_validation_persistence_plan_from_temp_file,
    delete_uploaded_document_records,
    list_recent_uploaded_documents,
    load_validation_payload_temp_file,
    persist_validation_result_with_temp_handoff,
    table_counts,
    write_validation_payload_temp_file,
)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_validation_persistence_plan_uses_real_document_pipeline_output():
    result, fixture_file = _actual_validation_result()

    plan = build_validation_persistence_plan(
        result,
        uploaded_by_user_id=os.environ.get("STATS_TEST_USER_ID", "local-real-fixture-user"),
        storage_reference=f"local-file://tests/input/{fixture_file.name}",
    )
    counts = table_counts(plan.operations)

    assert result["document"]["original_filename"] == fixture_file.name
    assert result["parse_id"].startswith("parse_")
    assert result["extraction_id"].startswith("extract_")
    assert result["validation_id"].startswith("validate_")
    assert counts["validation_results"] == 1
    assert counts["stats_documents"] == 1
    assert counts["processing_runs"] == 1
    assert counts["transaction_batches"] == 1
    assert counts.get("transactions", 0) == result["summary"]["normalized_record_count"]
    assert counts.get("financial_fields", 0) == result["summary"]["financial_field_count"]
    assert counts.get("document_sections", 0) == result["summary"]["section_candidate_count"]
    assert counts.get("validated_entities", 0) == result["summary"]["entity_count"]
    assert counts.get("validated_references", 0) == result["summary"]["reference_count"]
    assert counts.get("line_items", 0) == result["summary"]["line_item_count"]
    assert counts.get("installments", 0) == result["summary"]["installment_count"]
    if result["document_financial_summary"]:
        assert counts.get("statement_summaries", 0) == 1
        assert counts.get("document_financial_summaries", 0) == 1

    staging = _only(plan, "validation_results")
    assert staging["payload_json"].startswith("{")
    assert staging["section_candidate_count"] == result["summary"]["section_candidate_count"]
    assert staging["entity_count"] == result["summary"]["entity_count"]
    assert staging["reference_count"] == result["summary"]["reference_count"]
    assert fixture_file.name in staging["payload_json"]

    document = _only(plan, "stats_documents")
    assert document["original_filename"] == fixture_file.name
    assert document["storage_reference"] == f"local-file://tests/input/{fixture_file.name}"
    assert re.fullmatch(r"[0-9a-f]{64}", document["document_fingerprint"])

    if result["normalized_records"]:
        transaction = _only(plan, "transactions")
        assert transaction["normalized_description"]
        assert transaction["duplicate_key"]
        assert transaction["source_candidate_id"] == result["normalized_records"][0]["source_candidate_id"]
        assert transaction["transaction_type"] == result["normalized_records"][0].get("transaction_type", "unknown")
        assert transaction["transaction_subtype"] == result["normalized_records"][0].get("transaction_subtype", "unknown")
        assert transaction["spending_category"] == result["normalized_records"][0].get("spending_category", "uncategorized")
        assert transaction["spending_subcategory"] == result["normalized_records"][0].get("spending_subcategory", "unknown")
        assert "classification_review_reason_codes_json" in transaction
        assert "recognition_suggestion_id" in transaction
        assert "recognition_suggestion_status" in transaction
        assert "suggested_transaction_type" in transaction
        assert "suggested_spending_category" in transaction
        assert "suggestion_reason_codes_json" in transaction

    if result["document_financial_summary"]:
        statement_summary = _only(plan, "statement_summaries")
        document_financial_summary = _only(plan, "document_financial_summaries")
        assert statement_summary["document_id"] == plan.document_id
        assert document_financial_summary["document_id"] == plan.document_id
        assert statement_summary["quality_status"] in {"valid", "warning", "invalid"}
        assert document_financial_summary["quality_status"] in {"valid", "warning", "invalid"}


def test_build_validation_persistence_plan_persists_recognition_suggestion_row():
    result, _fixture_file = _actual_validation_result()
    record = result["normalized_records"][0]
    record.update(
        {
            "recognition_suggestion_id": "suggestion_test_123",
            "recognition_suggestion_status": "pending",
            "transaction_type": "unknown",
            "transaction_subtype": "unknown",
            "spending_category": "uncategorized",
            "spending_subcategory": "unknown",
            "suggested_transaction_type": "membership_topup",
            "suggested_transaction_subtype": "transport_card_topup",
            "suggested_spending_category": "public_transport",
            "suggested_spending_subcategory": "stored_value_topup",
            "suggestion_confidence": 0.91,
            "suggestion_reason_codes": ["AI_RECOGNITION_LABEL_SUGGESTION"],
            "suggestion_source": "ai",
            "suggestion_evidence_ref": "candidate:txn_0001",
        }
    )

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    suggestion = _only(plan, "recognition_label_suggestions")

    assert suggestion["suggestion_id"] == "suggestion_test_123"
    assert suggestion["source_module"] == "M7"
    assert suggestion["suggestion_status"] == "pending"
    assert suggestion["current_transaction_type"] == "unknown"
    assert suggestion["suggested_transaction_type"] == "membership_topup"
    assert suggestion["suggested_spending_category"] == "public_transport"
    assert suggestion["suggestion_source"] == "ai"


def test_build_validation_persistence_plan_skips_admin_suggestion_for_human_confirmed_classification():
    result, _fixture_file = _actual_validation_result()
    record = result["normalized_records"][0]
    record.update(
        {
            "classification_human_confirmed": True,
            "classification_confirmation_mode": "upload_transaction_review",
            "classification_source": "user_confirmed_ai_suggestion",
            "classification_vocabulary_status": "outside_vocabulary_proposal",
            "recognition_suggestion_id": "suggestion_confirmed_123",
            "recognition_suggestion_status": "confirmed_by_upload_review",
            "transaction_type": "membership_topup",
            "transaction_subtype": "transport_card_topup",
            "spending_category": "public_transport",
            "spending_subcategory": "stored_value_topup",
            "suggested_transaction_type": "membership_topup",
            "suggested_transaction_subtype": "transport_card_topup",
            "suggested_spending_category": "public_transport",
            "suggested_spending_subcategory": "stored_value_topup",
        }
    )

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")

    assert not [operation for operation in plan.operations if operation.table == "recognition_label_suggestions"]
    assert transaction["transaction_type"] == "membership_topup"
    assert transaction["spending_category"] == "public_transport"
    assert transaction["classification_human_confirmed"] == 1
    assert transaction["recognition_suggestion_id"] is None
    assert transaction["recognition_suggestion_status"] == "none"


def test_build_validation_persistence_plan_derives_category_parent_from_reviewed_subcategory():
    result = {
        "validation_id": "validate_parent_derivation",
        "status": "completed",
        "document_type": "statement",
        "summary": {
            "normalized_record_count": 1,
            "valid_record_count": 1,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "evaluation": {},
        "document": {
            "ingestion_id": "ingest_parent_derivation",
            "original_filename": "reviewed-transaction.pdf",
            "normalized_filename": "reviewed-transaction.pdf",
        },
        "normalized_records": [
            {
                "record_id": "record_1",
                "source_candidate_id": "txn_1",
                "transaction_date": "2026-06-16",
                "description": "Immigration Agency Service",
                "amount": 125.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -125.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "classification_human_confirmed": True,
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_source": "user_confirmed_classification",
                "transaction_type": "unknown",
                "transaction_subtype": "professional_service",
                "spending_category": "uncategorized",
                "spending_subcategory": "immigration_services",
            }
        ],
    }

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")

    assert transaction["transaction_type"] == "purchase"
    assert transaction["transaction_subtype"] == "professional_service"
    assert transaction["spending_category"] == "professional_services"
    assert transaction["spending_subcategory"] == "immigration_services"
    assert transaction["category"] == "Professional Services"
    assert transaction["classification_human_confirmed"] == 1


def test_build_validation_persistence_plan_derives_shopping_parent_from_clothing_subcategory():
    result = {
        "validation_id": "validate_clothing_parent_derivation",
        "status": "completed",
        "document_type": "statement",
        "summary": {
            "normalized_record_count": 1,
            "valid_record_count": 1,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "evaluation": {},
        "document": {
            "ingestion_id": "ingest_clothing_parent_derivation",
            "original_filename": "reviewed-clothing.pdf",
            "normalized_filename": "reviewed-clothing.pdf",
        },
        "normalized_records": [
            {
                "record_id": "record_1",
                "source_candidate_id": "txn_1",
                "transaction_date": "2026-06-16",
                "description": "Clothing Store",
                "amount": 45.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -45.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "classification_human_confirmed": True,
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_source": "user_confirmed_classification",
                "transaction_type": "purchase",
                "transaction_subtype": "merchant_purchase",
                "spending_category": "uncategorized",
                "spending_subcategory": "clothing",
            }
        ],
    }

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")

    assert transaction["spending_category"] == "shopping"
    assert transaction["spending_subcategory"] == "clothing"


def test_build_validation_persistence_plan_derives_parent_from_active_context_maps():
    result = {
        "validation_id": "validate_dynamic_parent_derivation",
        "status": "completed",
        "document_type": "statement",
        "summary": {
            "normalized_record_count": 1,
            "valid_record_count": 1,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "evaluation": {},
        "document": {
            "ingestion_id": "ingest_dynamic_parent_derivation",
            "original_filename": "reviewed-dynamic-parent.pdf",
            "normalized_filename": "reviewed-dynamic-parent.pdf",
        },
        "normalized_records": [
            {
                "record_id": "record_1",
                "source_candidate_id": "txn_1",
                "transaction_date": "2026-06-16",
                "description": "Dynamic Admin Label",
                "amount": 45.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -45.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "classification_human_confirmed": True,
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_source": "user_confirmed_classification",
                "transaction_type": "unknown",
                "transaction_subtype": "visa_fee",
                "transaction_subtype_parent_map": {"visa_fee": "fee"},
                "spending_category": "uncategorized",
                "spending_subcategory": "pet_grooming",
                "spending_subcategory_parent_map": {"pet_grooming": "pets"},
            }
        ],
    }

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")

    assert transaction["transaction_type"] == "fee"
    assert transaction["transaction_subtype"] == "visa_fee"
    assert transaction["spending_category"] == "pets"
    assert transaction["spending_subcategory"] == "pet_grooming"


def test_build_validation_persistence_plan_keeps_missing_record_ids_distinct():
    result = {
        "validation_id": "validate_missing_record_ids",
        "status": "completed",
        "document_type": "statement",
        "summary": {
            "normalized_record_count": 2,
            "valid_record_count": 2,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "evaluation": {},
        "document": {
            "ingestion_id": "ingest_missing_record_ids",
            "original_filename": "missing-record-ids.pdf",
            "normalized_filename": "missing-record-ids.pdf",
        },
        "normalized_records": [
            {
                "transaction_date": "2026-06-16",
                "description": "First Missing Id",
                "amount": 10.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -10.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "transaction_type": "purchase",
                "transaction_subtype": "merchant_purchase",
                "spending_category": "shopping",
                "spending_subcategory": "general_merchandise",
            },
            {
                "transaction_date": "2026-06-16",
                "description": "Second Missing Id",
                "amount": 20.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -20.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "transaction_type": "purchase",
                "transaction_subtype": "merchant_purchase",
                "spending_category": "transport",
                "spending_subcategory": "rideshare",
            },
        ],
    }

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transactions = [operation.values for operation in plan.operations if operation.table == "transactions"]

    assert len(transactions) == 2
    assert transactions[0]["transaction_id"] != transactions[1]["transaction_id"]


def test_persistence_parent_maps_cover_committed_vocabularies():
    transaction_vocabulary = _load_json(REPO_ROOT / "config" / "transaction-classification.vocabulary.json")
    spending_vocabulary = _load_json(REPO_ROOT / "config" / "spending-category.vocabulary.json")

    transaction_children = {
        child
        for children in transaction_vocabulary["transaction_subtypes"].values()
        for child in children
        if child != "unknown"
    }
    spending_children = {
        child
        for children in spending_vocabulary["spending_subcategories"].values()
        for child in children
        if child != "unknown"
    }

    assert transaction_children <= set(TRANSACTION_SUBTYPE_PARENT_MAP)
    assert spending_children <= set(SPENDING_SUBCATEGORY_PARENT_MAP)


def test_ai_suggestion_activation_requires_matching_suggested_label():
    record = {
        "classification_human_confirmed": True,
        "classification_source": "user_confirmed_ai_suggestion",
        "classification_confirmation_mode": "upload_transaction_review",
        "classification_vocabulary_status": "outside_vocabulary_proposal",
        "recognition_suggestion_id": "",
        "transaction_type": "purchase",
        "transaction_subtype": "merchant_purchase",
        "spending_category": "shopping",
        "spending_subcategory": "clothing",
        "suggested_transaction_type": "transfer",
        "suggested_transaction_subtype": "bank_transfer",
        "suggested_spending_category": "transfers",
        "suggested_spending_subcategory": "bank_transfer",
    }

    assert _classification_activation_allowed(record) is False


def test_activate_confirmed_classifications_upserts_labels_and_audit_rows():
    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "classification_human_confirmed": True,
                "classification_source": "user_confirmed_ai_suggestion",
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_vocabulary_status": "outside_vocabulary_proposal",
                "recognition_suggestion_id": "suggestion_confirmed_1",
                "transaction_type": "membership_topup",
                "transaction_subtype": "transport_card_topup",
                "spending_category": "public_transport",
                "spending_subcategory": "stored_value_topup",
                "suggested_transaction_type": "membership_topup",
                "suggested_transaction_subtype": "transport_card_topup",
                "suggested_spending_category": "public_transport",
                "suggested_spending_subcategory": "stored_value_topup",
            }
        ]
    }

    _activate_confirmed_classifications(cursor, result, saved_by_user_id="user_1")

    sql_text = "\n".join(sql for sql, _params in cursor.calls)
    params = [params for _sql, params in cursor.calls]

    assert "INSERT INTO dbo.recognition_labels" in sql_text
    assert "MERGE dbo.recognition_config_changes" in sql_text
    assert any(
        len(call_params) > 2 and call_params[1] == "transaction" and call_params[2] == "membership_topup"
        for call_params in params
    )
    assert any("transaction:membership_topup" in call_params for call_params in params)


def test_unconfirmed_outside_vocabulary_label_persists_fallback_and_admin_suggestion():
    result, _fixture_file = _actual_validation_result()
    record = result["normalized_records"][0]
    record.update(
        {
            "classification_human_confirmed": False,
            "classification_vocabulary_status": "outside_vocabulary_proposal",
            "recognition_suggestion_id": "suggestion_unconfirmed_123",
            "recognition_suggestion_status": "outside_vocabulary",
            "transaction_type": "membership_topup",
            "transaction_subtype": "transport_card_topup",
            "spending_category": "public_transport",
            "spending_subcategory": "stored_value_topup",
            "suggested_transaction_type": "membership_topup",
            "suggested_transaction_subtype": "transport_card_topup",
            "suggested_spending_category": "public_transport",
            "suggested_spending_subcategory": "stored_value_topup",
        }
    )

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")
    suggestion = _only(plan, "recognition_label_suggestions")

    assert transaction["transaction_type"] == "unknown"
    assert transaction["spending_category"] == "uncategorized"
    assert transaction["recognition_suggestion_id"] == "suggestion_unconfirmed_123"
    assert suggestion["suggested_transaction_type"] == "membership_topup"


def test_user_confirmed_outside_vocabulary_bypasses_admin_suggestion_trace():
    result = {
        "validation_id": "validate_user_confirmed_outside_vocab",
        "status": "completed",
        "document_type": "statement",
        "summary": {
            "normalized_record_count": 1,
            "valid_record_count": 1,
            "warning_record_count": 0,
            "invalid_record_count": 0,
            "duplicate_record_count": 0,
        },
        "evaluation": {},
        "document": {
            "ingestion_id": "ingest_user_confirmed_outside_vocab",
            "original_filename": "reviewed-transaction.pdf",
            "normalized_filename": "reviewed-transaction.pdf",
        },
        "normalized_records": [
            {
                "record_id": "record_1",
                "source_candidate_id": "txn_1",
                "transaction_date": "2026-06-16",
                "description": "Transit card top up",
                "amount": 45.0,
                "currency": "NZD",
                "direction": "debit",
                "signed_amount": -45.0,
                "confidence": 0.94,
                "quality_status": "valid",
                "classification_human_confirmed": True,
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_source": "user_confirmed_classification",
                "classification_vocabulary_status": "outside_vocabulary_proposal",
                "recognition_suggestion_id": "suggestion_rules_123",
                "recognition_suggestion_status": "confirmed_by_upload_review",
                "transaction_type": "membership_topup",
                "transaction_subtype": "transport_card_topup",
                "spending_category": "public_transport",
                "spending_subcategory": "stored_value_topup",
                "suggested_transaction_type": "membership_topup",
                "suggested_transaction_subtype": "transport_card_topup",
                "suggested_spending_category": "public_transport",
                "suggested_spending_subcategory": "stored_value_topup",
                "suggestion_source": "rules",
            }
        ],
    }

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    transaction = _only(plan, "transactions")

    assert transaction["transaction_type"] == "membership_topup"
    assert transaction["recognition_suggestion_id"] is None
    assert transaction["recognition_suggestion_status"] == "none"
    assert transaction["classification_human_confirmed"] == 1
    assert not [operation for operation in plan.operations if operation.table == "recognition_label_suggestions"]


def test_client_confirmation_without_review_shape_does_not_activate_label():
    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "classification_human_confirmed": True,
                "classification_source": "unknown",
                "classification_confirmation_mode": "upload_transaction_review",
                "transaction_type": "tax_evasion_crypto",
                "transaction_subtype": "unknown",
                "spending_category": "uncategorized",
                "spending_subcategory": "unknown",
            }
        ]
    }

    _activate_confirmed_classifications(cursor, result, saved_by_user_id="user_1")

    assert cursor.calls == []


def test_ai_confirmed_label_activation_requires_full_parent_child_match():
    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "classification_human_confirmed": True,
                "classification_source": "user_confirmed_ai_suggestion",
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_vocabulary_status": "outside_vocabulary_proposal",
                "recognition_suggestion_id": "suggestion_confirmed_2",
                "transaction_type": "membership_topup",
                "transaction_subtype": "top_up",
                "spending_category": "uncategorized",
                "spending_subcategory": "unknown",
                "suggested_transaction_type": "membership_topup",
                "suggested_transaction_subtype": "unknown",
            }
        ]
    }

    _activate_confirmed_classifications(cursor, result, saved_by_user_id="user_1")

    assert cursor.calls == []


def test_user_entered_spending_subcategory_activation_without_admin_suggestion():
    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "classification_human_confirmed": True,
                "classification_source": "user_confirmed_classification",
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_vocabulary_status": "outside_vocabulary_proposal",
                "transaction_type": "purchase",
                "transaction_subtype": "professional_service",
                "spending_category": "professional_services",
                "spending_subcategory": "immigration_services",
            }
        ]
    }

    _activate_confirmed_classifications(cursor, result, saved_by_user_id="user_1")

    sql_text = "\n".join(sql for sql, _params in cursor.calls)
    params = [params for _sql, params in cursor.calls]

    assert "INSERT INTO dbo.recognition_labels" in sql_text
    assert any(
        len(call_params) > 4 and call_params[1] == "spending" and call_params[2] == "professional_services" and call_params[4] == '["uncategorized", "immigration_services"]'
        for call_params in params
    )


def test_generic_human_override_does_not_learn_merchant_profile():
    from stats_data.validation_persistence import _upsert_learned_merchant_classifications

    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "description": "One Off Merchant",
                "classification_human_confirmed": True,
                "classification_source": "user_confirmed_classification",
                "classification_confirmation_mode": "upload_transaction_review",
                "transaction_type": "purchase",
                "transaction_subtype": "merchant_purchase",
                "spending_category": "shopping",
                "spending_subcategory": "retail",
            }
        ]
    }

    _upsert_learned_merchant_classifications(cursor, result, validation_id="validate_1", owner_id="user_1")

    assert cursor.calls == []


def test_user_added_classification_can_learn_merchant_profile():
    from stats_data.validation_persistence import _upsert_learned_merchant_classifications

    cursor = _FakeRecognitionCursor()
    result = {
        "normalized_records": [
            {
                "record_id": "record_1",
                "description": "New Learned Merchant",
                "classification_human_confirmed": True,
                "classification_source": "user_confirmed_classification",
                "classification_confirmation_mode": "upload_transaction_review",
                "classification_user_added_spending_subcategory": True,
                "transaction_type": "purchase",
                "transaction_subtype": "merchant_purchase",
                "spending_category": "shopping",
                "spending_subcategory": "clothing",
            }
        ]
    }

    _upsert_learned_merchant_classifications(cursor, result, validation_id="validate_1", owner_id="user_1")

    sql_text = "\n".join(sql for sql, _params in cursor.calls)
    assert "merchant_classification_profiles" in sql_text


def test_build_validation_persistence_plan_persists_document_recognition_suggestion_row():
    result, _fixture_file = _actual_validation_result()
    result.update(
        {
            "document_type": "unknown",
            "document_recognition_suggestion_id": "doc_suggestion_test_123",
            "document_recognition_suggestion_status": "pending",
            "suggested_document_type": "receipt",
            "suggested_document_subtype": "tax_receipt",
            "document_suggestion_confidence": 0.91,
            "document_suggestion_reason_codes": ["AI_SUGGESTED_INACTIVE_DOCUMENT_LABEL"],
            "document_suggestion_source": "m5_ai_document_classification",
            "document_suggestion_evidence_ref": "m5:redacted_classification_prompt",
        }
    )

    plan = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    document = _only(plan, "stats_documents")
    suggestion = next(
        operation.values
        for operation in plan.operations
        if operation.table == "recognition_label_suggestions" and operation.values["source_module"] == "M5"
    )

    assert document["document_type"] == "unknown"
    assert document["recognition_suggestion_id"] == "doc_suggestion_test_123"
    assert document["recognition_suggestion_status"] == "pending"
    assert document["suggested_document_type"] == "receipt"
    assert suggestion["suggestion_id"] == "doc_suggestion_test_123"
    assert suggestion["source_module"] == "M5"
    assert suggestion["current_document_type"] == "unknown"
    assert suggestion["suggested_document_type"] == "receipt"
    assert suggestion["suggested_document_subtype"] == "tax_receipt"


def test_build_validation_persistence_plan_is_deterministic_for_real_validation_output():
    result, _fixture_file = _actual_validation_result()

    first = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")
    second = build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user")

    first_ids = [(operation.table, operation.values[operation.key_column]) for operation in first.operations]
    second_ids = [(operation.table, operation.values[operation.key_column]) for operation in second.operations]

    assert first.document_id == second.document_id
    assert first_ids == second_ids


def test_validation_temp_handoff_file_uses_central_configured_directory(monkeypatch, tmp_path):
    result, fixture_file = _actual_validation_result()
    handoff_dir = tmp_path / "configured-validation-handoff"
    monkeypatch.setenv("STATS_VALIDATION_HANDOFF_DIR", str(handoff_dir))

    handoff_file = write_validation_payload_temp_file(result)
    loaded_result = load_validation_payload_temp_file(handoff_file)
    plan = build_validation_persistence_plan_from_temp_file(
        handoff_file,
        uploaded_by_user_id="local-real-fixture-user",
        storage_reference=f"local-file://tests/input/{fixture_file.name}",
    )

    assert handoff_file.exists()
    assert handoff_file.parent == handoff_dir
    assert handoff_file.name.endswith(".validation.json")
    assert loaded_result["validation_id"] == result["validation_id"]
    assert loaded_result["document"]["original_filename"] == fixture_file.name
    assert plan.validation_id == result["validation_id"]
    assert _only(plan, "stats_documents")["original_filename"] == fixture_file.name


def test_persist_validation_result_writes_real_fixture_to_configured_azure_sql():
    connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING", "").strip()
    if not connection_string:
        pytest.skip("Set AZURE_SQL_CONNECTIONSTRING to run the live M9 Azure SQL persistence test.")

    pyodbc = pytest.importorskip("pyodbc")
    from apply_azure_sql_migrations import _apply_migration, _normalize_connection_string

    result, fixture_file = _actual_validation_result()
    connection = pyodbc.connect(_normalize_connection_string(connection_string), timeout=30, autocommit=False)

    try:
        cursor = connection.cursor()
        for migration_file in sorted((REPO_ROOT / "apps" / "stats-data" / "migrations" / "azure-sql").glob("*.sql")):
            _apply_migration(cursor, migration_file)
            connection.commit()

        temp_dir = REPO_ROOT / "tests" / "results" / "m9-live-handoff"
        plan = persist_validation_result_with_temp_handoff(
            connection,
            result,
            temp_dir=temp_dir,
            uploaded_by_user_id=os.environ.get("STATS_TEST_USER_ID", "local-real-fixture-user"),
            storage_reference=f"local-file://tests/input/{fixture_file.name}",
        )

        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT vr.validation_id, sd.original_filename, vr.promotion_status
            FROM dbo.validation_results AS vr
            INNER JOIN dbo.stats_documents AS sd
                ON sd.validation_result_id = vr.validation_result_id
            WHERE vr.validation_result_id = ?
            """,
            plan.validation_result_id,
        )
        row = cursor.fetchone()

        assert row is not None
        assert row.validation_id == result["validation_id"]
        assert row.original_filename == fixture_file.name
        assert row.promotion_status == "promoted"
        assert not list(temp_dir.glob(f"{result['validation_id']}*.validation.json"))
    finally:
        connection.close()


def test_delete_uploaded_document_records_removes_child_rows_before_document():
    connection = _FakeDeleteConnection()

    result = delete_uploaded_document_records(connection, "document_1")

    delete_tables = [
        entry["table"]
        for entry in connection.cursor_instance.executions
        if entry["kind"] == "delete"
    ]

    assert result.document_id == "document_1"
    assert result.validation_result_id == "validation_result_1"
    assert result.deleted_counts["stats_documents"] == 1
    assert result.deleted_counts["validation_results"] == 1
    assert result.deleted_counts["duplicate_check_results"] == 1
    assert result.deleted_counts["duplicate_check_batches"] == 1
    assert delete_tables.index("duplicate_check_results") < delete_tables.index("transactions")
    assert delete_tables.index("duplicate_check_results") < delete_tables.index("duplicate_check_batches")
    assert delete_tables.index("duplicate_check_batches") < delete_tables.index("stats_documents")
    assert delete_tables.index("review_items") < delete_tables.index("transactions")
    assert delete_tables.index("findings") < delete_tables.index("transactions")
    assert delete_tables.index("transactions") < delete_tables.index("transaction_batches")
    assert delete_tables.index("transaction_batches") < delete_tables.index("stats_documents")
    assert delete_tables.index("stats_documents") < delete_tables.index("validation_results")
    assert connection.committed is True
    assert connection.rolled_back is False


def test_list_recent_uploaded_documents_returns_frontend_summary_rows():
    connection = _FakeListConnection()

    documents = list_recent_uploaded_documents(connection, limit=5)

    assert len(documents) == 1
    assert documents[0].document_id == "document_1"
    assert documents[0].original_filename == "201911_BPICHK.pdf"
    assert documents[0].transaction_count == 16
    assert documents[0].financial_field_count == 9
    assert documents[0].review_item_count == 15
    assert "fetch next ? rows only" in connection.cursor_instance.executed_sql.lower()
    assert "desc;\noffset" not in connection.cursor_instance.executed_sql.lower()
    assert connection.cursor_instance.executed_params == (5,)
    assert connection.cursor_instance.executed_sql.lower().find("stats_documents") < connection.cursor_instance.executed_sql.lower().find("order by")
    assert connection.cursor_instance.closed is True


def test_validation_results_retry_does_not_reset_promotion_state():
    result, _fixture_file = _actual_validation_result()
    operation = _only_operation(
        build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user"),
        "validation_results",
    )
    cursor = _FakeMergeCursor()

    _execute_insert_if_missing(cursor, operation)

    sql = cursor.executed_sql.lower()
    assert "[promotion_status] = target.[promotion_status]" in sql

    _mark_promoted(cursor, operation.values["validation_result_id"])
    promotion_sql = cursor.executed_sql.lower()
    assert "promotion_error = case when promotion_status = ?" in promotion_sql
    assert "promoted_at_utc = coalesce(promoted_at_utc, sysutcdatetime())" in promotion_sql


def test_stats_documents_retry_preserves_existing_storage_reference_when_source_is_empty():
    result, _fixture_file = _actual_validation_result()
    operation = _only_operation(
        build_validation_persistence_plan(result, uploaded_by_user_id="local-real-fixture-user"),
        "stats_documents",
    )
    operation.values["storage_reference"] = ""
    cursor = _FakeMergeCursor()

    _execute_insert_if_missing(cursor, operation)

    assert "coalesce(nullif(src.[storage_reference], ''), target.[storage_reference])" in cursor.executed_sql.lower()


def _actual_validation_result() -> tuple[dict[str, Any], Path]:
    for fixture_file in _real_input_files():
        try:
            result = _run_document_validation_pipeline(fixture_file)
        except Exception:
            continue
        if result["summary"]["normalized_record_count"] or result["summary"]["financial_field_count"]:
            return result, fixture_file

    pytest.skip("No configured tests/input fixture produced validation output for M9 persistence.")


def _run_document_validation_pipeline(fixture_file: Path) -> dict[str, Any]:
    parsing_root = REPO_ROOT / "modules" / "document-parsing-module"
    _activate_app_module(parsing_root)
    from app.services.parsing_service import parse_document_content

    content = fixture_file.read_bytes()
    content_type = mimetypes.guess_type(fixture_file.name)[0]
    parsed = parse_document_content(
        content=content,
        filename=fixture_file.name,
        provided_content_type=content_type,
        ingestion_id=f"ingest_{fixture_file.stem.lower()}",
        source_type="configured_test_input",
        source_id=str(fixture_file.relative_to(REPO_ROOT)).replace("\\", "/"),
        allow_ocr_fallback=fixture_file.suffix.lower() not in {".pdf"},
        page_limit=int(os.environ.get("STATS_TEST_PAGE_LIMIT", "2")),
    )

    extraction_root = REPO_ROOT / "modules" / "transaction-extraction-module"
    _activate_app_module(extraction_root)
    from app.models.extraction import TransactionExtractionRequest
    from app.services.extraction_service import extract_transactions

    extraction_request = TransactionExtractionRequest(
        parse_id=parsed.parse_id,
        document=_dump_model(parsed.document),
        document_type=parsed.classification.document_type,
        classification_confidence=parsed.classification.confidence,
        classification=_dump_model(parsed.classification),
        text=parsed.text,
        pages=[_dump_model(page) for page in parsed.pages],
        metadata=_dump_model(parsed.metadata),
        quality=_dump_model(parsed.quality),
        findings=[_dump_model(finding) for finding in parsed.findings],
    )
    extracted = extract_transactions(extraction_request)

    validation_root = REPO_ROOT / "modules" / "data-validation-module"
    _activate_app_module(validation_root)
    from app.models.validation import DataValidationRequest
    from app.services.validation_service import validate_data

    validation_request = DataValidationRequest(
        extraction_id=extracted.extraction_id,
        parse_id=extracted.parse_id,
        document=_dump_model(extracted.document),
        document_type=extracted.document_type,
        transaction_candidates=[_dump_model(candidate) for candidate in extracted.transaction_candidates],
        financial_field_candidates=[_dump_model(candidate) for candidate in extracted.financial_field_candidates],
        section_candidates=[_dump_model(candidate) for candidate in extracted.section_candidates],
        entity_candidates=[_dump_model(candidate) for candidate in extracted.entity_candidates],
        reference_candidates=[_dump_model(candidate) for candidate in extracted.reference_candidates],
        line_item_candidates=[_dump_model(candidate) for candidate in extracted.line_item_candidates],
        installment_candidates=[_dump_model(candidate) for candidate in extracted.installment_candidates],
        reconciliation=_dump_model(extracted.reconciliation),
        findings=[_dump_model(finding) for finding in extracted.findings],
    )
    return _dump_model(validate_data(validation_request))


def _real_input_files() -> list[Path]:
    configured = os.environ.get("STATS_TESTDATA_DIR")
    input_dir = Path(configured) if configured else REPO_ROOT / "tests" / "input"
    if not input_dir.exists():
        pytest.skip(f"Configured real test-data directory does not exist: {input_dir}")

    explicit_fixture = os.environ.get("STATS_M9_TEST_FIXTURE")
    if explicit_fixture:
        fixture_file = Path(explicit_fixture)
        if not fixture_file.is_absolute():
            fixture_file = input_dir / fixture_file
        if not fixture_file.exists():
            pytest.skip(f"Configured STATS_M9_TEST_FIXTURE does not exist: {fixture_file}")
        return [fixture_file]

    suffixes = {".pdf", ".png", ".jpg", ".jpeg"}
    files = [path for path in sorted(input_dir.iterdir()) if path.is_file() and path.suffix.lower() in suffixes]
    if not files:
        pytest.skip(f"No real document fixtures found in configured test-data directory: {input_dir}")

    return sorted(files, key=lambda path: (path.suffix.lower() != ".pdf", path.name.lower()))


def _activate_app_module(module_root: Path) -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]
    module_root_path = str(module_root)
    if module_root_path in sys.path:
        sys.path.remove(module_root_path)
    sys.path.insert(0, module_root_path)


def _dump_model(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


def _only(plan, table):
    return [operation.values for operation in plan.operations if operation.table == table][0]


def _only_operation(plan, table):
    return [operation for operation in plan.operations if operation.table == table][0]


class _FakeRow:
    def __init__(self, *values):
        self._values = values

    def __getitem__(self, index):
        return self._values[index]


class _FakeDeleteCursor:
    def __init__(self):
        self.executions = []
        self.rowcount = -1
        self._next_row = None

    def execute(self, sql, *params):
        normalized = " ".join(sql.split()).lower()
        table = _delete_table_name(normalized)
        if normalized.startswith("select validation_result_id"):
            self._next_row = _FakeRow("validation_result_1")
            self.rowcount = -1
            self.executions.append({"kind": "select", "table": "stats_documents", "params": params})
        elif normalized.startswith("select count(1)"):
            self._next_row = _FakeRow(0)
            self.rowcount = -1
            self.executions.append({"kind": "select", "table": "stats_documents", "params": params})
        elif normalized.startswith("delete"):
            self._next_row = None
            self.rowcount = 1
            self.executions.append({"kind": "delete", "table": table, "params": params})
        else:
            self._next_row = None
            self.rowcount = 1
            self.executions.append({"kind": "statement", "table": table, "params": params})
        return self

    def fetchone(self):
        return self._next_row

    def close(self):
        self.closed = True


class _FakeDeleteConnection:
    def __init__(self):
        self.cursor_instance = _FakeDeleteCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _FakeListRow:
    document_id = "document_1"
    original_filename = "201911_BPICHK.pdf"
    document_type = "statement"
    status = "needs_review"
    source_institution = "BPI"
    created_at_utc = "2026-06-05T11:41:23"
    updated_at_utc = "2026-06-05T11:41:23"
    uploaded_by_user_id = "user_1"
    storage_reference = "local-file://tests/input/201911_BPICHK.pdf"
    validation_result_id = "validation_result_1"
    transaction_count = 16
    financial_field_count = 9
    review_item_count = 15


class _FakeListCursor:
    def __init__(self):
        self.executed_sql = ""
        self.executed_params = ()
        self.closed = False

    def execute(self, sql, *params):
        self.executed_sql = sql
        self.executed_params = params
        return self

    def fetchall(self):
        return [_FakeListRow()]

    def close(self):
        self.closed = True


class _FakeMergeCursor:
    def __init__(self):
        self.executed_sql = ""
        self.executed_params = ()

    def execute(self, sql, *params):
        self.executed_sql = sql
        self.executed_params = params
        return self


class _FakeRecognitionCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return None


class _FakeListConnection:
    def __init__(self):
        self.cursor_instance = _FakeListCursor()

    def cursor(self):
        return self.cursor_instance


def _delete_table_name(normalized_sql: str) -> str | None:
    match = re.search(r"(?:delete from|update) dbo\.([a-z_]+)", normalized_sql)
    return match.group(1) if match else None
