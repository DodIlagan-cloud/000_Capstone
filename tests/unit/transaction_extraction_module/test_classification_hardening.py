"""M7 - Transaction Extraction Module Start
Tests transaction classification resilience hardening.
M7 End"""

import json
import sys
import urllib.error
from io import BytesIO
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "transaction-extraction-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
module_root_path = str(MODULE_ROOT)
if module_root_path in sys.path:
    sys.path.remove(module_root_path)
sys.path.insert(0, module_root_path)

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


def test_ai_http_quota_error_reports_quota_exhausted(monkeypatch):
    candidate = TransactionCandidate(
        candidate_id="txn_quota",
        description="SUPERBOWL MANDALUYONG OF CHINA PH",
        amount=1382.51,
        currency="PHP",
        direction="debit",
        source=SourceReference(line_number=1, text="SUPERBOWL MANDALUYONG OF CHINA PH 1,382.51"),
        confidence=0.9,
    )
    body = {
        "error": {
            "code": 429,
            "message": "Quota exceeded",
            "status": "RESOURCE_EXHAUSTED",
        }
    }

    def fake_urlopen(*_args, **_kwargs):
        raise urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=BytesIO(json.dumps(body).encode("utf-8")),
        )

    monkeypatch.setenv("TEST_GEMINI_API_KEY", "configured-for-test")
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_enabled", True)
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_provider", "gemini")
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_model", "gemini-2.5-flash")
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_api_key_env", "TEST_GEMINI_API_KEY")
    monkeypatch.setattr(ai_transaction_classification_service.urllib.request, "urlopen", fake_urlopen)

    result = ai_transaction_classification_service.ai_classify_transaction(
        candidate=candidate,
        document_type="statement",
        document_subtype="credit_card_statement",
        transaction_result={"label": "purchase", "status": "classified", "confidence": 0.78},
        category_result={"label": "uncategorized", "status": "unknown", "confidence": 0.0},
    )

    assert result is None
    assert (
        ai_transaction_classification_service.ai_classification_failure_reason()
        == ai_transaction_classification_service.AI_SKIP_PROVIDER_QUOTA_EXHAUSTED
    )


def test_openai_provider_uses_default_chat_completions_endpoint(monkeypatch):
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_provider", "openai")
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_endpoint", "")

    assert ai_transaction_classification_service._request_endpoint() == "https://api.openai.com/v1/chat/completions"


def test_prior_merchant_classification_is_reused_before_ai(monkeypatch):
    candidate = TransactionCandidate(
        candidate_id="txn_learned",
        description="Grabtaxi Phils - Ipg",
        amount=250.0,
        currency="PHP",
        direction="debit",
        source=SourceReference(line_number=1, text="Grabtaxi Phils - Ipg 250.00", section_label="transaction_table"),
        confidence=0.9,
    )
    active_settings = {
        "recognition_context_version": "ctx_learned",
        "transaction_vocabulary": {
            "transaction_types": ["purchase", "unknown"],
            "transaction_subtypes": {"purchase": ["merchant_purchase", "unknown"], "unknown": ["unknown"]},
        },
        "spending_vocabulary": {
            "spending_categories": ["transport", "uncategorized"],
            "spending_subcategories": {"transport": ["rideshare", "unknown"], "uncategorized": ["unknown"]},
        },
        "transaction_rules": {"rules": []},
        "spending_rules": {"rules": []},
    }

    def fail_ai(*_args, **_kwargs):
        raise AssertionError("AI should not be called when learned merchant classification is safe")

    monkeypatch.setattr(transaction_classification_service, "_load_active_settings", lambda: active_settings)
    monkeypatch.setattr(
        transaction_classification_service,
        "_learned_merchant_classification",
        lambda **_kwargs: {
            "match_status": "matched",
            "transaction_type": "purchase",
            "transaction_subtype": "merchant_purchase",
            "spending_category": "transport",
            "spending_subcategory": "rideshare",
            "profile_confidence": 0.92,
            "reason_codes": ["PRIOR_MERCHANT_CLASSIFICATION_REUSED"],
        },
    )
    monkeypatch.setattr(transaction_classification_service, "ai_classify_transaction", fail_ai)

    classified = transaction_classification_service.classify_transaction_candidate(
        candidate,
        document_type="statement",
        document_subtype="credit_card_statement",
    )

    assert classified.transaction_type == "purchase"
    assert classified.transaction_subtype == "merchant_purchase"
    assert classified.spending_category == "transport"
    assert classified.spending_subcategory == "rideshare"
    assert classified.classification_source == "prior_merchant_human_confirmed"
    assert classified.classification_review_required is False
    assert "PRIOR_MERCHANT_CLASSIFICATION_REUSED" in classified.spending_category_reason_codes


def test_prior_merchant_classification_is_reused_when_direction_is_unknown(monkeypatch):
    candidate = TransactionCandidate(
        candidate_id="txn_learned_unknown_direction",
        description="Grabtaxi Phils - Ipg",
        amount=250.0,
        currency="PHP",
        direction="unknown",
        source=SourceReference(line_number=1, text="Grabtaxi Phils - Ipg 250.00", section_label="transaction_table"),
        confidence=0.9,
    )
    active_settings = {
        "recognition_context_version": "ctx_learned",
        "transaction_vocabulary": {
            "transaction_types": ["purchase", "unknown"],
            "transaction_subtypes": {"purchase": ["merchant_purchase", "unknown"], "unknown": ["unknown"]},
        },
        "spending_vocabulary": {
            "spending_categories": ["transport", "uncategorized"],
            "spending_subcategories": {"transport": ["rideshare", "unknown"], "uncategorized": ["unknown"]},
        },
        "transaction_rules": {"rules": []},
        "spending_rules": {"rules": []},
    }

    def fail_ai(*_args, **_kwargs):
        raise AssertionError("AI should not be called when learned merchant classification is safe")

    monkeypatch.setattr(transaction_classification_service, "_load_active_settings", lambda: active_settings)
    monkeypatch.setattr(
        transaction_classification_service,
        "_learned_merchant_classification",
        lambda **_kwargs: {
            "match_status": "matched",
            "transaction_type": "purchase",
            "transaction_subtype": "merchant_purchase",
            "spending_category": "transport",
            "spending_subcategory": "rideshare",
            "profile_confidence": 0.92,
            "reason_codes": ["PRIOR_MERCHANT_CLASSIFICATION_REUSED"],
        },
    )
    monkeypatch.setattr(transaction_classification_service, "ai_classify_transaction", fail_ai)

    classified = transaction_classification_service.classify_transaction_candidate(
        candidate,
        document_type="statement",
        document_subtype="credit_card_statement",
    )

    assert classified.spending_subcategory == "rideshare"
    assert classified.classification_source == "prior_merchant_human_confirmed"
    assert classified.classification_review_required is False


def test_transaction_ai_conflict_preserves_non_conflicting_ai_category(monkeypatch):
    monkeypatch.setattr(ai_transaction_classification_service.settings, "transaction_classification_ai_min_confidence", 0.76)
    candidate = TransactionCandidate(
        candidate_id="txn_ai_category",
        description="ABC Immigration Services",
        amount=125.0,
        currency="NZD",
        direction="debit",
        source=SourceReference(line_number=1, text="ABC Immigration Services NZD 125.00"),
        confidence=0.9,
    )

    merged = ai_transaction_classification_service.merge_rule_and_ai_classification(
        candidate=candidate,
        rule_transaction={
            "label": "purchase",
            "subtype": "merchant_purchase",
            "confidence": 0.78,
            "status": "classified",
            "reason_codes": ["CREDIT_CARD_STATEMENT_DEBIT_PURCHASE"],
            "scores": {"statement.debit.purchase.merchant_purchase": 0.78},
        },
        rule_category={
            "label": "uncategorized",
            "subtype": "unknown",
            "confidence": 0.0,
            "status": "unknown",
            "reason_codes": ["NO_CLASSIFICATION_SIGNALS"],
            "scores": {},
        },
        ai_result={
            "transaction_type": "payment",
            "transaction_subtype": "invoice_payment",
            "spending_category": "professional_services",
            "spending_subcategory": "immigration_services",
            "confidence": 0.91,
            "reason_codes": ["AI_PROFESSIONAL_SERVICE"],
            "requires_review": True,
            "review_reason_codes": ["RULE_AI_TRANSACTION_TYPE_CONFLICT"],
            "ai_model_name": "gemini-2.5-flash",
            "ai_model_version": "gemini-2.5-flash",
        },
    )

    assert merged["classification_source"] == "rules_ai_conflict"
    assert merged["transaction"]["label"] == "purchase"
    assert merged["category"]["label"] == "professional_services"
    assert merged["category"]["subtype"] == "immigration_services"
    assert "RULE_AI_TRANSACTION_TYPE_CONFLICT" in merged["classification_review_reason_codes"]
