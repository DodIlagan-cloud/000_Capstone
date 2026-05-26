"""M2 - Stats Web Shell Start
Verifies the Stats Web local orchestration contract for sibling module APIs.
M2 End"""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATS_WEB_ROOT = REPO_ROOT / "apps" / "stats-web"
APPSETTINGS_FILE = STATS_WEB_ROOT / "appsettings.json"
PROGRAM_FILE = STATS_WEB_ROOT / "Program.cs"


def _load_appsettings() -> dict:
    return json.loads(APPSETTINGS_FILE.read_text(encoding="utf-8"))


def test_stats_web_registers_local_service_orchestrator():
    """Ensure the web shell starts the hosted orchestration service."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "StatsLocalServiceOrchestrator" in program_source
    assert "AddHostedService<StatsLocalServiceOrchestrator>()" in program_source
    assert "StatsWeb:Azure:Environment" in program_source


def test_local_orchestration_is_enabled_for_m2_shell():
    """Ensure local runs are configured to start missing sibling services."""
    appsettings = _load_appsettings()
    orchestration = appsettings["StatsWeb"]["LocalOrchestration"]

    assert orchestration["Enabled"] is True
    assert orchestration["StartMissingServices"] is True
    assert orchestration["HealthCheckTimeoutSeconds"] >= 1


def test_local_orchestration_declares_identity_and_file_intake_services():
    """Ensure the shell knows the current local module API health endpoints."""
    appsettings = _load_appsettings()
    stats_api_base_url = appsettings["StatsApi"]["BaseUrl"].rstrip("/")
    file_validation_base_url = appsettings["StatsWeb"]["Downstream"]["FileValidationBaseUrl"].rstrip("/")
    file_ingestion_base_url = appsettings["StatsWeb"]["Downstream"]["FileIngestionBaseUrl"].rstrip("/")
    services = {
        service["Name"]: service
        for service in appsettings["StatsWeb"]["LocalOrchestration"]["Services"]
    }

    assert services["Identity Access API"]["HealthUrl"] == f"{stats_api_base_url}/health"
    assert services["File Validation API"]["HealthUrl"] == f"{file_validation_base_url}/health"
    assert file_ingestion_base_url == file_validation_base_url
    assert "File Ingestion API" not in services


def test_local_orchestration_service_definitions_point_to_existing_modules():
    """Ensure configured local working directories exist and run uvicorn module apps."""
    appsettings = _load_appsettings()
    services = appsettings["StatsWeb"]["LocalOrchestration"]["Services"]

    for service in services:
        service_root = (STATS_WEB_ROOT / service["WorkingDirectory"]).resolve()

        assert service_root.exists()
        assert service["Command"] == "python"
        assert "-m uvicorn app.main:app" in service["Arguments"]
        assert "API_HOST" in service["Environment"]
        assert "API_PORT" in service["Environment"]
