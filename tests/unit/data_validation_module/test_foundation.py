"""M8 - Data Validation Module Start
Verifies the standalone Data Validation Module application foundation.
M8 End"""

def test_app_imports_successfully(module_app):
    assert module_app.title == "Data Validation Module"


def test_health_endpoint(client):
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["service"] == "Data Validation Module"
    assert payload["version"] == "1.0.0"
    assert payload["validation"]["default_currency"] == "PHP"
    assert payload["validation"]["duplicate_detection_enabled"] is True


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Data Validation Module",
        "version": "1.0.0",
        "message": "Data Validation Module is running",
    }


def test_settings_configured_values(monkeypatch, settings_cls):
    monkeypatch.setenv("MIN_RECORD_CONFIDENCE", "0.72")
    monkeypatch.setenv("ENABLE_DUPLICATE_DETECTION", "false")
    settings = settings_cls()

    assert settings.app_name == "Data Validation Module"
    assert settings.api_prefix == "/api/v1"
    assert settings.api_port == 8017
    assert settings.min_record_confidence == 0.72
    assert settings.enable_duplicate_detection is False
