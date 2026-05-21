"""Foundation module tests."""

from app.config import Settings
from app.db import init_db
from app.main import app


def test_app_imports_successfully():
    assert app.title == "Stats Ingestion Service"


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Stats Ingestion Service",
        "version": "1.0.0",
    }


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Stats Ingestion Service",
        "version": "1.0.0",
        "message": "Stats Ingestion Service is running",
    }


def test_settings_defaults():
    settings = Settings()

    assert settings.app_name == "Stats Ingestion Service"
    assert settings.app_version == "1.0.0"
    assert settings.api_prefix == "/api/v1"
    assert settings.max_file_size_mb == 50
    assert settings.allowed_extensions == ["pdf"]
    assert settings.database_url == "sqlite:///./stats_ingestion.db"


def test_database_initialization_is_callable():
    assert callable(init_db)
