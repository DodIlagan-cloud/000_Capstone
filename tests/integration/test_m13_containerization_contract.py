# M13 - Containerization Start
# Verifies the M13 single Stats runtime container contract.
# Checks that required infrastructure files exist and contain the expected content.
#
# TESTING BOUNDARY:
#   This file runs on the host with pytest -- no Docker or network required.
#   Runtime acceptance evidence (OCR, DB, cross-module) runs via:
#     tests/scripts/regression/run_docker_full_regression_evidence.ps1

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


# -- File existence -----------------------------------------------------------

def test_dockerfile_exists():
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"


def test_startup_script_exists():
    assert STARTUP_SCRIPT.exists(), f"Startup script not found at {STARTUP_SCRIPT}"


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


# -- Startup script content ---------------------------------------------------

def test_startup_script_waits_for_database():
    content = STARTUP_SCRIPT.read_text()
    assert "wait_for_database" in content, "Startup script must wait for the database before starting Identity API"


def test_startup_script_runs_identity_db_init():
    content = STARTUP_SCRIPT.read_text()
    assert "init_db" in content, "Startup script must run identity DB init before starting the Identity API"


def test_startup_script_starts_identity_api():
    assert "8013" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_file_validation_api():
    assert "8014" in STARTUP_SCRIPT.read_text()


def test_startup_script_starts_document_parsing_api():
    assert "8015" in STARTUP_SCRIPT.read_text()


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

def test_compose_has_stats_db_service():
    assert "stats-db" in COMPOSE_FILE.read_text(), \
        "Compose file must define a stats-db PostgreSQL service"


def test_compose_has_persistent_volume():
    assert "stats-db-data" in COMPOSE_FILE.read_text(), \
        "Compose file must define a stats-db-data persistent volume"


def test_compose_database_url_points_to_stats_db():
    content = COMPOSE_FILE.read_text()
    assert "stats-db" in content and "DATABASE_URL" in content, \
        "Compose file must wire DATABASE_URL to the stats-db service"


def test_compose_stats_depends_on_stats_db():
    content = COMPOSE_FILE.read_text()
    assert "depends_on" in content and "stats-db" in content, \
        "stats service must depend on stats-db"


def test_compose_exposes_stats_web_port():
    assert "8080" in COMPOSE_FILE.read_text()


def test_compose_references_dockerfile():
    assert "Dockerfile" in COMPOSE_FILE.read_text()


# -- Stats Web /health --------------------------------------------------------

def test_stats_web_exposes_health_endpoint():
    assert "/health" in STATS_WEB_PROGRAM.read_text(), \
        "Stats Web Program.cs must map a /health endpoint for container health checks"


def test_stats_web_proxies_browser_api_calls():
    content = STATS_WEB_PROGRAM.read_text()
    assert '"/api/v1/{**path}"' in content
    assert "StatsWebApiProxy.ProxyApiRequestAsync" in content
    assert "StatsWeb:Proxy:IdentityBaseUrl" in content
    assert "StatsWeb:Proxy:DocumentParsingBaseUrl" in content


def test_startup_script_keeps_browser_api_base_urls_same_origin():
    content = STARTUP_SCRIPT.read_text()
    assert '--StatsApi:BaseUrl ""' in content
    assert '--StatsWeb:Downstream:FileValidationBaseUrl ""' in content
    assert '--StatsWeb:Downstream:FileIngestionBaseUrl ""' in content
    assert '--StatsWeb:Downstream:DocumentParsingBaseUrl ""' in content
    assert "--StatsWeb:Proxy:IdentityBaseUrl" in content
    assert "--StatsWeb:Proxy:FileValidationBaseUrl" in content
    assert "--StatsWeb:Proxy:DocumentParsingBaseUrl" in content


# -- Env example content ------------------------------------------------------

def test_env_example_documents_postgres_vars():
    content = ENV_EXAMPLE.read_text()
    assert "POSTGRES_USER" in content
    assert "POSTGRES_PASSWORD" in content
    assert "POSTGRES_DB" in content


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


def test_docker_regression_runner_targets_stats_runtime():
    content = REGRESSION_RUNNER.read_text()
    assert "stats-runtime" in content, \
        "Regression script must target the stats-runtime container"


def test_docker_regression_runner_targets_stats_db():
    content = REGRESSION_RUNNER.read_text()
    assert "stats-db" in content, \
        "Regression script must verify the stats-db service"


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
        "Regression script must document the unit-test vs Docker-evidence testing boundary"

# M13 End
