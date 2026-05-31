"""M2 - Stats Web Shell Start
Verifies the M13 container-first Stats Web downstream configuration.
M2 End"""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATS_WEB_ROOT = REPO_ROOT / "apps" / "stats-web"
APPSETTINGS_FILE = STATS_WEB_ROOT / "appsettings.json"
PROGRAM_FILE = STATS_WEB_ROOT / "Program.cs"
UPLOAD_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "upload.js"
RUNTIME_CONFIG_FILE = REPO_ROOT / "config" / "stats.runtime.json"


def _load_appsettings() -> dict:
    return json.loads(APPSETTINGS_FILE.read_text(encoding="utf-8"))


def _load_runtime_config() -> dict:
    return json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))


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
    assert "NormalizeCorrelationId" in program_source
    assert "LOG_INCLUDE_CORRELATION_ID" in program_source
    assert "LOG_REDACT_SENSITIVE_VALUES" in program_source
    assert "LOG_DESTINATION" in program_source


def test_stats_web_uses_structured_startup_logging():
    """Ensure central config startup output goes through the configured logger."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "app.Logger.LogInformation" in program_source
    assert "Loaded central config" in program_source
    assert "Console.WriteLine" not in program_source


def test_stats_web_validates_required_proxy_ports_at_startup():
    """Ensure missing central module ports fail early instead of producing later empty proxy URLs."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "ValidateRequiredProxyPorts" in program_source
    assert "IDENTITY_PORT" in program_source
    assert "FILE_VALIDATION_PORT" in program_source
    assert "DOCUMENT_PARSING_PORT" in program_source
    assert "TRANSACTION_EXTRACTION_PORT" in program_source
    assert "DATA_VALIDATION_PORT" in program_source


def test_stats_web_resolves_local_paths_from_central_runtime():
    """Ensure local orchestration resolves paths from STATS_APP_ROOT/path config."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "ResolveAppRoot" in program_source
    assert "config/stats.paths.json" in program_source
    assert "centralRuntime.ResolvePath(configuredPath)" in program_source
    assert "Path.Combine(environment.ContentRootPath" not in program_source


def test_stats_web_cors_defaults_are_explicit_and_comma_separated():
    """Ensure CORS defaults do not collapse multiple origins into one malformed origin."""
    runtime_config = _load_runtime_config()
    cors_default = runtime_config["network"]["CORS_ALLOWED_ORIGINS"]["default"]
    origins = [origin.strip() for origin in cors_default.split(",") if origin.strip()]

    assert origins == ["http://localhost:8080", "http://127.0.0.1:8080"]
    assert "8080http" not in cors_default


def test_stats_web_handles_empty_cors_origins_explicitly():
    """Ensure empty CORS config is intentionally skipped instead of silently registering an empty policy."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "if (centralRuntime.CorsAllowedOrigins.Count > 0)" in program_source
    assert 'app.UseCors("StatsCorsPolicy")' in program_source


def test_stats_web_reports_central_config_parse_failures():
    """Ensure malformed central config files produce descriptive startup errors."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "ParseConfigDocument" in program_source
    assert "could not parse the central" in program_source
    assert "JsonException" in program_source
    assert "Loaded central config" in program_source


def test_upload_js_treats_empty_base_urls_as_same_origin_proxy():
    """Ensure blank browser base URLs intentionally resolve to relative Stats Web proxy URLs."""
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")

    assert "function statsApiUrl" in upload_source
    assert "return normalizedBase ? `${normalizedBase}${normalizedPath}` : normalizedPath;" in upload_source
    assert 'statsApiUrl(fileValidationBaseUrl, "/api/v1/files/validate")' in upload_source
    assert 'statsApiUrl(fileIngestionBaseUrl, "/api/v1/ingestions")' in upload_source
    assert 'statsApiUrl(documentParsingBaseUrl, "/api/v1/parses")' in upload_source
    assert 'statsApiUrl(transactionExtractionBaseUrl, "/api/v1/extractions")' in upload_source
    assert 'statsApiUrl(dataValidationBaseUrl, "/api/v1/validations")' in upload_source
