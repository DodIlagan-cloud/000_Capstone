"""M5 - Document Parsing Module Start
Tests document classification resilience hardening.
M5/M6 End"""

import json

from app.models.parsing import ClassificationResult
from app.services import ai_classification_service, classification_service


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_document_settings_loader_uses_stale_cache_on_outage(monkeypatch):
    payload = {"document_vocabulary": {"document_types": ["receipt"]}}
    calls = {"count": 0, "header": ""}

    def fake_urlopen(request, *_args, **_kwargs):
        calls["count"] += 1
        calls["header"] = request.get_header("X-stats-internal-key") or ""
        if calls["count"] == 1:
            return _Response(payload)
        raise OSError("temporary outage")

    classification_service._clear_settings_cache()
    monkeypatch.setattr(classification_service.settings, "recognition_settings_url", "http://stats-data/settings")
    monkeypatch.setattr(classification_service.settings, "recognition_settings_internal_key", "unit-internal-key")
    monkeypatch.setattr(classification_service.settings, "recognition_settings_cache_seconds", -1)
    monkeypatch.setattr(classification_service, "urlopen", fake_urlopen)

    assert classification_service._load_active_settings() == payload
    assert classification_service._load_active_settings() == payload
    assert calls["header"] == "unit-internal-key"


def test_ai_merge_preserves_rule_based_pending_document_suggestion(monkeypatch):
    rule_result = ClassificationResult(
        document_type="unknown",
        document_subtype="unknown",
        confidence=0.72,
        status="unknown",
        reason_codes=["POSSIBLE_NEW_DOCUMENT_SHAPE"],
        requires_review=True,
        review_reason_codes=["PENDING_DOCUMENT_LABEL_SUGGESTION"],
        recognition_suggestion_status="pending",
        suggested_document_type="receipt",
        suggested_document_subtype="sales_receipt",
        suggestion_confidence=0.72,
        suggestion_reason_codes=["POSSIBLE_NEW_DOCUMENT_SHAPE"],
        suggestion_source="m5_content_shape",
        suggestion_evidence_ref="m5:content_shape",
    )
    ai_result = ClassificationResult(
        document_type="medical_invoice",
        document_subtype="unknown",
        confidence=0.91,
        status="classified",
        reason_codes=["AI_ASSISTED_CLASSIFICATION"],
        ai_model_name="test-model",
        ai_model_version="test-model",
        ai_confidence=0.91,
    )
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_min_confidence", 0.5)

    merged = ai_classification_service.merge_rule_and_ai_classification(
        rule_result=rule_result,
        ai_result=ai_result,
        approved_document_types={"statement", "invoice"},
    )

    assert merged.suggested_document_type == "receipt"
    assert merged.suggested_document_subtype == "sales_receipt"
    assert merged.suggestion_source == "m5_content_shape"
    assert merged.ai_model_name == "test-model"


def test_ai_request_payload_includes_active_document_recognition_context(monkeypatch):
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_provider", "gemini")
    rule_result = ClassificationResult(
        document_type="unknown",
        document_subtype="unknown",
        confidence=0.2,
        status="unknown",
        reason_codes=["NO_CLASSIFICATION_SIGNALS"],
    )

    payload = ai_classification_service._request_payload(
        "Tax invoice total due 55.00",
        ["receipt", "invoice", "unknown"],
        rule_result,
        {
            "version": "ctx_doc_1",
            "document": {
                "vocabulary": {
                    "document_types": ["receipt", "invoice", "unknown"],
                    "document_subtypes": {"receipt": ["payment_terminal_receipt"]},
                }
            },
        },
    )

    prompt = payload["contents"][0]["parts"][0]["text"]
    decoded = json.loads(prompt)

    assert decoded["active_recognition_context"]["version"] == "ctx_doc_1"
    assert decoded["active_recognition_context"]["document"]["vocabulary"]["document_types"] == [
        "receipt",
        "invoice",
        "unknown",
    ]


def test_ai_response_rejects_unsupported_label_without_outside_vocabulary_status(monkeypatch):
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_min_confidence", 0.5)
    raw_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "document_type": "CONFIDENTIAL_SYSTEM_FILE",
                                    "document_subtype": "unknown",
                                    "confidence": 0.99,
                                    "reason_codes": ["BAD_RESPONSE"],
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    result = ai_classification_service._parse_ai_response(json.dumps(raw_response), ["receipt", "invoice", "unknown"])

    assert result is None


def test_ai_response_allows_safe_outside_vocabulary_document_proposal(monkeypatch):
    monkeypatch.setattr(ai_classification_service.settings, "classification_ai_min_confidence", 0.5)
    raw_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "document_type": "insurance_statement",
                                    "document_subtype": "premium_statement",
                                    "confidence": 0.89,
                                    "reason_codes": ["AI_NEW_DOCUMENT_SHAPE"],
                                    "vocabulary_status": "outside_vocabulary_proposal",
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }

    result = ai_classification_service._parse_ai_response(json.dumps(raw_response), ["receipt", "invoice", "unknown"])

    assert result is not None
    assert result.document_type == "insurance_statement"
    assert result.classification_vocabulary_status == "outside_vocabulary_proposal"
