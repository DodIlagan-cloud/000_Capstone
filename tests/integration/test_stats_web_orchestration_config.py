"""M2 - Stats Web Shell Start
Verifies the M13 container-first Stats Web downstream configuration.
M2 End"""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATS_WEB_ROOT = REPO_ROOT / "apps" / "stats-web"
APPSETTINGS_FILE = STATS_WEB_ROOT / "appsettings.json"
PROGRAM_FILE = STATS_WEB_ROOT / "Program.cs"


def _load_appsettings() -> dict:
    return json.loads(APPSETTINGS_FILE.read_text(encoding="utf-8"))


def test_stats_web_keeps_local_orchestrator_disabled_by_default():
    """Ensure host-side process startup is not the default test/runtime path."""
    # M13 - Containerization Start
    appsettings = _load_appsettings()
    orchestration = appsettings["StatsWeb"]["LocalOrchestration"]

    assert orchestration["Enabled"] is False
    assert orchestration["StartMissingServices"] is False
    assert orchestration["Services"] == []
    # M13 End


def test_stats_web_uses_same_origin_proxy_for_browser_downstream_calls():
    """Ensure browser module calls route through Stats Web instead of direct container-internal ports."""
    # M13 - Containerization Start
    appsettings = _load_appsettings()
    downstream = appsettings["StatsWeb"]["Downstream"]

    assert appsettings["StatsApi"]["BaseUrl"].rstrip("/") == "http://127.0.0.1:8013"
    assert downstream["FileValidationBaseUrl"].rstrip("/") == "http://127.0.0.1:8014"
    assert downstream["FileIngestionBaseUrl"].rstrip("/") == "http://127.0.0.1:8014"
    assert downstream["DocumentParsingBaseUrl"].rstrip("/") == "http://127.0.0.1:8015"
    # M13 End
    # M7 - Transaction Extraction Start
    assert downstream["TransactionExtractionBaseUrl"] == ""
    # M7 End
    # M8 - Data Validation Module Start
    assert downstream["DataValidationBaseUrl"] == ""
    # M8 End


def test_stats_web_program_allows_container_environment_overrides():
    """Ensure the container can override downstream URLs through environment variables."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "STATS_API_BASE_URL" in program_source
    assert "StatsWeb:Downstream:FileValidationBaseUrl" in program_source
    assert "StatsWeb:Downstream:FileIngestionBaseUrl" in program_source
    assert "StatsWeb:Downstream:DocumentParsingBaseUrl" in program_source
    assert "StatsWeb:Downstream:TransactionExtractionBaseUrl" in program_source
    assert "StatsWeb:Downstream:DataValidationBaseUrl" in program_source
