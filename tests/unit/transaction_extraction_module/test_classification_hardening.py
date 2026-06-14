"""M7 - Transaction Extraction Module Start
Tests transaction classification resilience hardening.
M7 End"""

import json

from app.models.extraction import SourceReference, TransactionCandidate
from app.services import ai_transaction_classification_service, transaction_classification_service


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_transaction_settings_loader_uses_stale_cache_on_outage(monkeypatch):
    payload = {"transaction_vocabulary": {"transaction_types": ["purchase"]}}
    calls = {"count": 0, "header": ""}

    def fake_urlopen(request, *_args, **_kwargs):
        calls["count"] += 1
        calls["header"] = request.get_header("X-stats-internal-key") or ""
        if calls["count"] == 1:
            return _Response(payload)
        raise OSError("temporary outage")

    transaction_classification_service._clear_settings_cache()
    monkeypatch.setattr(transaction_classification_service.settings, "recognition_settings_url", "http://stats-data/settings")
    monkeypatch.setattr(transaction_classification_service.settings, "recognition_settings_internal_key", "unit-internal-key")
    monkeypatch.setattr(transaction_classification_service.settings, "recognition_settings_cache_seconds", -1)
    monkeypatch.setattr(transaction_classification_service, "urlopen", fake_urlopen)

    assert transaction_classification_service._load_active_settings() == payload
    assert transaction_classification_service._load_active_settings() == payload
    assert calls["header"] == "unit-internal-key"


def test_ai_prompt_limiting_preserves_valid_json():
    user_prompt = {
        "document_type": "receipt",
        "candidate": {
            "description": "Receipt purchase",
            "source_text": "A" * 5000,
        },
    }

    encoded = ai_transaction_classification_service._encode_limited_user_prompt(user_prompt, 250)

    assert len(encoded) <= 250
    decoded = json.loads(encoded)
    assert decoded["candidate"]["description"] == "Receipt purchase"
    assert len(decoded["candidate"]["source_text"]) < 5000


def test_ai_prompt_limiting_enforces_budget_when_non_source_fields_are_large():
    user_prompt = {
        "document_type": "receipt",
        "document_subtype": "sales_receipt",
        "rule_transaction_result": {"reason_codes": ["RULE"] * 300, "scores": {f"r{i}": 0.1 for i in range(200)}},
        "rule_spending_category_result": {"reason_codes": ["CATEGORY_RULE"] * 300},
        "candidate": {
            "description": "A" * 2000,
            "amount": 42.5,
            "currency": "NZD",
            "direction": "debit",
            "source_text": "B" * 5000,
            "reason_codes": ["SOURCE"] * 300,
        },
    }

    encoded = ai_transaction_classification_service._encode_limited_user_prompt(user_prompt, 300)

    assert len(encoded) <= 300
    decoded = json.loads(encoded)
    assert decoded["candidate"]["source_text"] == ""
    assert len(decoded["candidate"]["description"]) < 2000


def test_ai_request_payload_includes_active_recognition_context(monkeypatch):
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_provider", "gemini")
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_max_chars", 5000)
    candidate = TransactionCandidate(
        candidate_id="txn_context",
        description="HOP card topup",
        amount=55.0,
        currency="NZD",
        direction="debit",
        source=SourceReference(line_number=1, text="HOP card topup NZD55.00"),
        confidence=0.9,
    )
    context = {
        "version": "ctx_test_1",
        "transaction": {"vocabulary": {"transaction_types": ["purchase", "unknown"]}},
        "spending": {"vocabulary": {"spending_categories": ["transport", "uncategorized"]}},
    }

    payload = ai_transaction_classification_service._request_payload(
        candidate=candidate,
        document_type="receipt",
        document_subtype="payment_terminal_receipt",
        transaction_result={"label": "unknown", "status": "unknown"},
        category_result={"label": "uncategorized", "status": "unknown"},
        active_recognition_context=context,
    )

    prompt = payload["contents"][0]["parts"][0]["text"]
    decoded = json.loads(prompt)

    assert decoded["active_recognition_context"]["version"] == "ctx_test_1"
    assert decoded["active_recognition_context"]["transaction"]["vocabulary"]["transaction_types"] == ["purchase", "unknown"]
