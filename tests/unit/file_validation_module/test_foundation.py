"""M3 - File Validation Module Start
Verifies the standalone File Validation Module application foundation.
M3 End"""

from app.config import Settings
from app.main import app


def test_app_imports_successfully():
    assert app.title == "File Validation Module"


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "File Validation Module",
        "version": "1.0.0",
    }


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "File Validation Module",
        "version": "1.0.0",
        "message": "File Validation Module is running",
    }


def test_settings_configured_values(monkeypatch):
    monkeypatch.delenv("MAX_FILE_SIZE_BYTES", raising=False)
    monkeypatch.setenv("STORAGE_ROOT", "configured-intake-root")
    settings = Settings()

    assert settings.app_name == "File Validation Module"
    assert settings.api_prefix == "/api/v1"
    assert settings.max_file_size_bytes == 10485760
    assert ".pdf" in settings.allowed_extensions
    assert settings.default_workflow == "document-processing"
    assert settings.storage_root.name == "configured-intake-root"
