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
