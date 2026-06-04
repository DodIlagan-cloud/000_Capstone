# M13 - Containerization Start
# Verifies the M13 single Stats runtime container contract.
# Checks that required infrastructure files exist and contain the expected content.
#
# TESTING BOUNDARY:
#   From M13 onward, official execution of this contract belongs inside the
#   Stats runtime container via tests/scripts/regression/run_module_unit_tests.ps1.

from pathlib import Path

REPO_ROOT       = Path(__file__).parent.parent.parent
DOCKERFILE      = REPO_ROOT / "infrastructure" / "containers" / "stats" / "Dockerfile"
STARTUP_SCRIPT  = REPO_ROOT / "infrastructure" / "containers" / "stats" / "start-stats-runtime.sh"
COMPOSE_FILE    = REPO_ROOT / "infrastructure" / "compose" / "stats-runtime.compose.yml"
ENV_EXAMPLE     = REPO_ROOT / "infrastructure" / "containers" / "stats" / ".env.container.example"
STATS_WEB_PROGRAM = REPO_ROOT / "apps" / "stats-web" / "Program.cs"
TEST_INPUT_DIR  = REPO_ROOT / "tests/input"
EVIDENCE_RUNNER = REPO_ROOT / "tests/scripts" / "M13-Containerization" / "run_docker_acceptance_evidence.ps1"
REGRESSION_RUNNER = REPO_ROOT / "tests/scripts" / "regression" / "run_docker_full_regression_evidence.ps1"
MODULE_UNIT_RUNNER = REPO_ROOT / "tests/scripts" / "regression" / "run_module_unit_tests.ps1"


# -- File existence -----------------------------------------------------------

def test_dockerfile_exists():
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"


def test_startup_script_exists():
    assert STARTUP_SCRIPT.exists(), f"Startup script not found at {STARTUP_SCRIPT}"


def test_admin_bootstrap_runner_is_packaged_separately_from_startup():
    runner = REPO_ROOT / "infrastructure" / "containers" / "stats" / "run-stats-admin-bootstrap.sh"
    assert runner.exists(), f"Admin bootstrap runner not found at {runner}"

    dockerfile = DOCKERFILE.read_text()
    startup = STARTUP_SCRIPT.read_text()
    runner_content = runner.read_text()

    assert "COPY infrastructure/containers/stats/run-stats-admin-bootstrap.sh" in dockerfile
    assert "chmod +x /app/start-stats-runtime.sh /app/run-stats-admin-bootstrap.sh" in dockerfile
    assert "app.scripts.create_admin" in runner_content
    assert "app.scripts.create_admin" not in startup


def test_startup_script_uses_lf_line_endings():
    content = STARTUP_SCRIPT.read_bytes()
    assert b"\r\n" not in content, "Startup script must use LF line endings for Linux container execution"


def test_compose_file_exists():
    assert COMPOSE_FILE.exists(), f"Compose file not found at {COMPOSE_FILE}"


def test_env_example_exists():
    assert ENV_EXAMPLE.exists(), f".env.container.example not found at {ENV_EXAMPLE}"


# -- Dockerfile content -------------------------------------------------------

def test_dockerfile_installs_tesseract():
    assert "tesseract-ocr" in DOCKERFILE.read_text(), "Dockerfile must install tesseract-ocr"


def test_dockerfile_installs_tessdata_eng():
    assert "tesseract-ocr-eng" in DOCKERFILE.read_text(), "Dockerfile must install English tessdata"


def test_dockerfile_sets_tesseract_env():
    content = DOCKERFILE.read_text()
    assert "TESSERACT_CMD" in content
    assert "TESSDATA_PREFIX" in content
    assert "ALLOW_OCR_FALLBACK" in content


def test_dockerfile_uses_dotnet9():
    content = DOCKERFILE.read_text()
    assert "aspnetcore-runtime-9.0" in content or "dotnet/sdk:9.0" in content


def test_dockerfile_verifies_tesseract_at_build_time():
    assert "tesseract --version" in DOCKERFILE.read_text(), \
        "Dockerfile must run 'tesseract --version' to verify install at build time"


def test_dockerfile_verifies_pymupdf_at_build_time():
    assert "import fitz" in DOCKERFILE.read_text(), \
        "Dockerfile must verify PyMuPDF (import fitz) at build time"


def test_dockerfile_verifies_pytesseract_at_build_time():
    assert "import pytesseract" in DOCKERFILE.read_text(), \
        "Dockerfile must verify pytesseract at build time"


def test_dockerfile_verifies_pillow_at_build_time():
    assert "from PIL import Image" in DOCKERFILE.read_text(), \
        "Dockerfile must verify Pillow at build time"


def test_dockerfile_installs_and_verifies_azure_sql_driver():
    content = DOCKERFILE.read_text()
    assert "msodbcsql18" in content, "Dockerfile must install the SQL Server ODBC driver"
    assert "unixodbc" in content, "Dockerfile must install unixODBC for pyodbc"
    assert "import pyodbc" in content, "Dockerfile must verify pyodbc at build time"


def test_dockerfile_copies_tests_for_container_execution():
    content = DOCKERFILE.read_text()
    assert "COPY tests/" in content, "Dockerfile must copy test code into the Stats runtime image"
    assert "COPY apps/stats-web/appsettings.json /app/apps/stats-web/appsettings.json" in content, \
        "Dockerfile must copy Stats Web appsettings for container-executed M2 config checks"


def test_dockerfile_copies_central_config_for_fail_fast_startup():
    content = DOCKERFILE.read_text()
    assert "COPY config/ /app/config/" in content, \
        "Dockerfile must copy central config files because Stats Web fails fast when they are missing"
    assert "STATS_RUNTIME_CONFIG=/app/config/stats.runtime.json" in content
    assert "STATS_PATHS_CONFIG=/app/config/stats.paths.json" in content
    assert "STATS_LOGGING_CONFIG=/app/config/stats.logging.json" in content


def test_dockerfile_packages_transaction_extraction_module():
    content = DOCKERFILE.read_text()
    assert "transaction-extraction-module" in content, "Dockerfile must package M7 in the Stats runtime image"


def test_dockerfile_packages_data_validation_module():
    content = DOCKERFILE.read_text()
    assert "data-validation-module" in content, "Dockerfile must package M8 in the Stats runtime image"


def test_dockerfile_packages_m9_azure_sql_migrations_without_intake_data():
    content = DOCKERFILE.read_text()
    dockerignore = (REPO_ROOT / ".dockerignore").read_text()
    assert "COPY apps/stats-data/migrations/ /app/apps/stats-data/migrations/" in content
    assert "COPY apps/stats-data/scripts/ /app/apps/stats-data/scripts/" in content
    assert "COPY apps/stats-data/ /app/apps/stats-data/" not in content
    assert "apps/stats-data/data/" in dockerignore


# -- Startup script content ---------------------------------------------------

def test_startup_script_waits_for_database():
    content = STARTUP_SCRIPT.read_text()
    assert "wait_for_database" in content, "Startup script must wait for the database before starting Identity API"
    assert "wait_for_azure_sql" in content, "Startup script must support Azure SQL readiness"


def test_startup_script_normalizes_azure_sql_odbc_connection_string():
    content = STARTUP_SCRIPT.read_text()
    assert "Driver={ODBC Driver 18 for SQL Server}" in content
    assert "Initial Catalog=" in content
    assert "Database=" in content
    assert "User ID=" in content
    assert "UID=" in content
    assert "Password=" in content
    assert "PWD=" in content
    assert "Encrypt=True" in content
    assert "Encrypt=yes" in content
    assert "TrustServerCertificate=False" in content
    assert "TrustServerCertificate=no" in content


def test_startup_script_runs_identity_db_init():
    content = STARTUP_SCRIPT.read_text()
    assert "init_db" in content, "Startup script must run identity DB init before starting the Identity API"


def test_startup_script_applies_m9_migrations_before_identity_db_init():
    lines = STARTUP_SCRIPT.read_text().splitlines()
    migration = [i for i, line in enumerate(lines) if "apply_azure_sql_migrations.py" in line]
    identity = [i for i, line in enumerate(lines) if "init_db" in line]
    assert migration, "Startup script must run M9 Azure SQL migrations"
    assert identity, "Startup script must run M1 identity DB init"
    assert min(migration) < min(identity), "M9 migrations must run before M1 identity init"


def test_startup_script_starts_identity_api():
    assert "8013" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_file_validation_api():
    assert "8014" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_document_parsing_api():
    assert "8015" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_transaction_extraction_api():
    assert "8016" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_data_validation_api():
    assert "8017" in STARTUP_SCRIPT.read_text()


def test_startup_script_performs_health_checks():
    content = STARTUP_SCRIPT.read_text()
    assert "wait_for_health" in content
    assert "curl" in content


def test_startup_script_health_checks_before_stats_web():
    lines = STARTUP_SCRIPT.read_text().splitlines()
    hc = [i for i, l in enumerate(lines) if "wait_for_health" in l]
    sw = [i for i, l in enumerate(lines) if "stats.Web.dll" in l]
    assert hc and sw and max(hc) < min(sw), \
        "All health checks must complete before Stats Web starts"


# -- Compose file content -----------------------------------------------------

def test_compose_uses_azure_sql_provider():
    content = COMPOSE_FILE.read_text()
    assert "DATABASE_PROVIDER" in content
    assert "AzureSql" in content
    assert "AZURE_SQL_CONNECTIONSTRING" in content


def test_compose_does_not_start_postgres_service():
    content = COMPOSE_FILE.read_text()
    assert "postgres:" not in content.lower()
    assert "stats-db:" not in content


def test_compose_database_connection_requires_ignored_local_secret_value():
    content = COMPOSE_FILE.read_text()
    assert (
        'AZURE_SQL_CONNECTIONSTRING: '
        '"${AZURE_SQL_CONNECTIONSTRING:?Set AZURE_SQL_CONNECTIONSTRING in infrastructure/compose/.env.container}"'
    ) in content


def test_compose_stats_has_no_database_container_dependency():
    content = COMPOSE_FILE.read_text()
    assert "depends_on" not in content


def test_compose_exposes_stats_web_port():
    content = COMPOSE_FILE.read_text()
    assert "${STATS_WEB_HOST_PORT:-8080}:${STATS_WEB_PORT:-8080}" in content
    assert 'STATS_WEB_PORT: "${STATS_WEB_PORT:-8080}"' in content


def test_compose_configures_data_validation_port():
    content = COMPOSE_FILE.read_text()
    assert 'TRANSACTION_EXTRACTION_PORT: "${TRANSACTION_EXTRACTION_PORT:-8016}"' in content
    assert 'DATA_VALIDATION_PORT: "${DATA_VALIDATION_PORT:-8017}"' in content


def test_compose_references_dockerfile():
    assert "Dockerfile" in COMPOSE_FILE.read_text()


# -- Stats Web /health --------------------------------------------------------

def test_stats_web_exposes_health_endpoint():
    assert "/health" in STATS_WEB_PROGRAM.read_text(), \
        "Stats Web Program.cs must map a /health endpoint for container health checks"


def test_dockerfile_declares_container_healthcheck():
    content = DOCKERFILE.read_text()
    assert "HEALTHCHECK" in content
    assert "/health" in content


def test_stats_web_proxies_browser_api_calls():
    content = STATS_WEB_PROGRAM.read_text()
    assert '"/api/v1/{**path}"' in content
    assert "StatsWebApiProxy.ProxyApiRequestAsync" in content
    assert "StatsWeb:Proxy:IdentityBaseUrl" in content
    assert "StatsWeb:Proxy:DocumentParsingBaseUrl" in content
    assert "StatsWeb:Proxy:TransactionExtractionBaseUrl" in content
    assert "StatsWeb:Proxy:DataValidationBaseUrl" in content


def test_startup_script_keeps_browser_api_base_urls_same_origin():
    content = STARTUP_SCRIPT.read_text()
    assert '--StatsApi:BaseUrl ""' in content
    assert '--StatsWeb:Downstream:FileValidationBaseUrl ""' in content
    assert '--StatsWeb:Downstream:FileIngestionBaseUrl ""' in content
    assert '--StatsWeb:Downstream:DocumentParsingBaseUrl ""' in content
    assert '--StatsWeb:Downstream:TransactionExtractionBaseUrl ""' in content
    assert '--StatsWeb:Downstream:DataValidationBaseUrl ""' in content
    assert "--StatsWeb:Proxy:IdentityBaseUrl" in content
    assert "--StatsWeb:Proxy:FileValidationBaseUrl" in content
    assert "--StatsWeb:Proxy:DocumentParsingBaseUrl" in content
    assert "--StatsWeb:Proxy:TransactionExtractionBaseUrl" in content
    assert "--StatsWeb:Proxy:DataValidationBaseUrl" in content


def test_stats_web_proxies_m7_and_m8_api_calls():
    content = STATS_WEB_PROGRAM.read_text()
    assert "path.StartsWith(\"extractions\"" in content
    assert "path.StartsWith(\"validations\"" in content
    assert "TransactionExtractionBaseUrl" in content
    assert "DataValidationBaseUrl" in content


# -- Env example content ------------------------------------------------------

def test_env_example_documents_azure_sql_vars():
    content = ENV_EXAMPLE.read_text()
    assert "DATABASE_PROVIDER=AzureSql" in content
    assert "DATABASE_SCHEMA=dbo" in content
    assert "AZURE_SQL_CONNECTIONSTRING" in content
    assert "POSTGRES_PASSWORD" not in content


def test_env_example_documents_ocr_variables():
    content = ENV_EXAMPLE.read_text()
    assert "ALLOW_OCR_FALLBACK" in content
    assert "OCR_ENGINE" in content
    assert "TESSERACT" in content


def test_env_example_documents_secret_key():
    assert "ACCESS_TOKEN_SECRET_KEY" in ENV_EXAMPLE.read_text()


# -- Evidence runner fixture policy ------------------------------------------

def test_m13_evidence_runner_uses_project_test_input():
    content = EVIDENCE_RUNNER.read_text()
    assert "tests/input" in content
    assert "docker cp" in content
    assert "stats-runtime" in content
    assert "/api/v1/parses" in content


def test_project_test_input_contains_real_files():
    assert TEST_INPUT_DIR.exists(), f"Required tests/input directory not found at {TEST_INPUT_DIR}"
    supported = {".jpg", ".jpeg", ".png", ".pdf"}
    files = [
        path for path in TEST_INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in supported
    ]
    assert files, "tests/input must contain at least one JPG, PNG, or PDF fixture"


# -- Docker full regression evidence runner -----------------------------------

def test_docker_regression_runner_exists():
    assert REGRESSION_RUNNER.exists(), \
        f"Docker full regression evidence script not found at {REGRESSION_RUNNER}"


def test_container_module_unit_runner_exists():
    assert MODULE_UNIT_RUNNER.exists(), \
        f"Container module unit runner not found at {MODULE_UNIT_RUNNER}"


def test_container_module_unit_runner_uses_docker_exec():
    content = MODULE_UNIT_RUNNER.read_text()
    assert "docker exec stats-runtime" in content
    assert "pytest" in content
    assert "/app/tests/input" in content
    assert "docker cp" in content
    assert "data_validation_module" in content


def test_container_module_unit_runner_cleans_up_by_default():
    content = MODULE_UNIT_RUNNER.read_text()
    assert "LeaveStackRunning" in content
    assert '"down"' in content


def test_docker_regression_runner_targets_stats_runtime():
    content = REGRESSION_RUNNER.read_text()
    assert "stats-runtime" in content, \
        "Regression script must target the stats-runtime container"


def test_docker_regression_runner_targets_stats_db():
    content = REGRESSION_RUNNER.read_text()
    assert "Azure SQL" in content or "AZURE_SQL" in content, \
        "Regression script must verify the Azure SQL database target"


def test_docker_regression_runner_uses_test_input():
    content = REGRESSION_RUNNER.read_text()
    assert "tests/input" in content, \
        "Regression script must use tests/input/ as the fixture source"


def test_docker_regression_runner_targets_stats_web_port():
    content = REGRESSION_RUNNER.read_text()
    assert "127.0.0.1:8080" in content, \
        "Regression script must target Stats Web at http://127.0.0.1:8080"


def test_docker_regression_runner_calls_parse_endpoint():
    content = REGRESSION_RUNNER.read_text()
    assert "/api/v1/parses" in content, \
        "Regression script must call /api/v1/parses for M5 document parsing evidence"


def test_docker_regression_runner_covers_m1_through_m5():
    content = REGRESSION_RUNNER.read_text()
    for module in ("M1", "M2", "M3", "M4", "M5"):
        assert module in content, f"Regression script must include {module} evidence"


def test_docker_regression_runner_uses_compose_env_file():
    content = REGRESSION_RUNNER.read_text()
    assert ".env.container" in content, \
        "Regression script must reference the .env.container secrets file"


def test_docker_regression_runner_does_not_expose_secrets():
    content = REGRESSION_RUNNER.read_text()
    assert "token_prefix" in content or "Substring" in content, \
        "Regression script must truncate tokens; full secrets must not be written to evidence files"


def test_docker_regression_runner_documents_testing_boundary():
    content = REGRESSION_RUNNER.read_text()
    assert "TESTING BOUNDARY" in content, \
        "Regression script must document the container-first testing boundary"

# M13 End
