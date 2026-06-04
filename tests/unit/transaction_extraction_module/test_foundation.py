"""M7 - Transaction Extraction Module Start
Verifies the standalone Transaction Extraction Module application foundation.
M7 End"""

def test_app_imports_successfully(module_app):
    assert module_app.title == "Transaction Extraction Module"


def test_health_endpoint(client):
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["service"] == "Transaction Extraction Module"
    assert payload["version"] == "1.0.0"
    assert payload["extraction"]["default_currency"] == "PHP"
    assert "statement" in payload["extraction"]["supported_document_types"]


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Transaction Extraction Module",
        "version": "1.0.0",
        "message": "Transaction Extraction Module is running",
    }


def test_settings_configured_values(monkeypatch, settings_cls):
    monkeypatch.setenv("SUPPORTED_DOCUMENT_TYPES", "statement,receipt,invoice,payment_proof,utility_bill,unknown")
    monkeypatch.setenv("MIN_TRANSACTION_CONFIDENCE", "0.61")
    settings = settings_cls()

    assert settings.app_name == "Transaction Extraction Module"
    assert settings.api_prefix == "/api/v1"
    assert settings.api_port == 8016
    assert settings.default_currency == "PHP"
    assert settings.min_transaction_confidence == 0.61
    assert settings.enable_field_extraction is True
    assert "invoice" in settings.supported_document_types
    assert "statement" in settings.supported_document_types
