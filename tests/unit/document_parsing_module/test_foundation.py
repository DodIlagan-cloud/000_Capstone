"""M5 - Document Parsing Module Start
Verifies the standalone Document Parsing Module application foundation.
M5/M6 End"""

from app.config import Settings
from app.main import app


def test_app_imports_successfully():
    assert app.title == "Document Parsing Module"


def test_health_endpoint(client):
    response = client.get("/health")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "healthy"
    assert payload["service"] == "Document Parsing Module"
    assert payload["version"] == "1.0.0"
    assert isinstance(payload["ocr"]["enabled"], bool)
    assert payload["ocr"]["engine"] in {"none", "tesseract"}
    assert payload["ocr"]["renderer"] == "PyMuPDF"
    assert "tesseract_available" in payload["ocr"]
    assert "renderer_available" in payload["ocr"]


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Document Parsing Module",
        "version": "1.0.0",
        "message": "Document Parsing Module is running",
    }


def test_settings_configured_values(monkeypatch):
    monkeypatch.setenv("SUPPORTED_DOCUMENT_TYPES", "statement,receipt,invoice,payment_proof,utility_bill,unknown")
    monkeypatch.delenv("TESSDATA_PREFIX", raising=False)
    settings = Settings()

    assert settings.app_name == "Document Parsing Module"
    assert settings.api_prefix == "/api/v1"
    assert settings.api_port == 8015
    assert "application/pdf" in settings.supported_mime_types
    assert "invoice" in settings.supported_document_types
    assert "statement" in settings.supported_document_types
    assert settings.document_classification_vocabulary_path.name == "document-classification.vocabulary.json"
    assert settings.document_classification_rules_path.name == "document-classification.rules.json"
    assert settings.redact_evidence_output is True
    assert settings.tessdata_prefix == ""
