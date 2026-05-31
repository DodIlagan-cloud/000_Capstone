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

    assert appsettings["StatsApi"]["BaseUrl"] == ""
    assert downstream["FileValidationBaseUrl"] == ""
    assert downstream["FileIngestionBaseUrl"] == ""
    assert downstream["DocumentParsingBaseUrl"] == ""
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

    assert "StatsCentralRuntime.Load" in program_source
    assert "STATS_RUNTIME_CONFIG" in program_source
    assert "STATS_PATHS_CONFIG" in program_source
    assert "STATS_LOGGING_CONFIG" in program_source
    assert "STATS_API_BASE_URL" in program_source
    assert "StatsWeb:Downstream:FileValidationBaseUrl" in program_source
    assert "StatsWeb:Downstream:FileIngestionBaseUrl" in program_source
    assert "StatsWeb:Downstream:DocumentParsingBaseUrl" in program_source
    assert "StatsWeb:Downstream:TransactionExtractionBaseUrl" in program_source
    assert "StatsWeb:Downstream:DataValidationBaseUrl" in program_source


def test_stats_web_wires_central_logging_and_correlation():
    """Ensure Stats Web consumes the central logging registry instead of only documenting it."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "StatsLoggingBootstrap.Configure" in program_source
    assert "LOG_LEVEL" in program_source
    assert "LOG_FORMAT" in program_source
    assert "AddJsonConsole" in program_source
    assert "StatsCorrelationMiddleware" in program_source
    assert "correlation_id" in program_source


def test_stats_web_resolves_local_paths_from_central_runtime():
    """Ensure local orchestration resolves paths from STATS_APP_ROOT/path config."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "ResolveAppRoot" in program_source
    assert "config/stats.paths.json" in program_source
    assert "centralRuntime.ResolvePath(configuredPath)" in program_source
    assert "Path.Combine(environment.ContentRootPath" not in program_source
