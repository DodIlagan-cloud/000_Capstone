"""M1 - User Access Management Start
Verifies the standalone Identity Access Module application foundation.
M1 End"""

from app.config import Settings
from app.db import init_db
from app.main import app


def test_app_imports_successfully():
    assert app.title == "Identity Access Module"


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "Identity Access Module",
        "version": "1.0.0",
    }


def test_root_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "Identity Access Module",
        "version": "1.0.0",
        "message": "Identity Access Module is running",
    }


# M1 - User Access Management Start
# Verifies the configured Azure SQL value independent of Module 1 test database overrides.
# def test_settings_defaults():
def test_settings_configured_values(monkeypatch):
    monkeypatch.setenv("DATABASE_PROVIDER", "AzureSql")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("AZURE_SQL_CONNECTIONSTRING", "Server=tcp:example.database.windows.net,1433;Initial Catalog=stats;Encrypt=True;")
    settings = Settings()

    assert settings.app_name == "Identity Access Module"
    assert settings.app_version == "1.0.0"
    assert settings.api_prefix == "/api/v1"
    assert settings.database_provider == "AzureSql"
    assert "example.database.windows.net" in settings.azure_sql_connectionstring
# M1 End


def test_database_initialization_is_callable():
    assert callable(init_db)
