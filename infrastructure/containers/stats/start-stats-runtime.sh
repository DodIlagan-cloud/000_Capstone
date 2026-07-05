#!/bin/bash
# M13 - Containerization Start
# Starts all Stats module APIs in order, waits for health checks, then starts Stats Web.
# Order: database ready -> migrations -> identity DB init -> module APIs -> Stats Data API -> Stats Web

set -e

# -- Configuration ------------------------------------------------------------
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-60}
STARTUP_DIAGNOSTIC_ON_FAILURE=${STARTUP_DIAGNOSTIC_ON_FAILURE:-false}
CONTAINER_TEST_MODE=${CONTAINER_TEST_MODE:-false}
STATS_APP_ROOT=${STATS_APP_ROOT:-/app}
STATS_RUNTIME_CONFIG=${STATS_RUNTIME_CONFIG:-${STATS_APP_ROOT}/config/stats.runtime.json}
STATS_PATHS_CONFIG=${STATS_PATHS_CONFIG:-${STATS_APP_ROOT}/config/stats.paths.json}
STATS_LOGGING_CONFIG=${STATS_LOGGING_CONFIG:-${STATS_APP_ROOT}/config/stats.logging.json}
STATS_STORAGE_PROVIDER=${STATS_STORAGE_PROVIDER:-LocalFileSystem}
STATS_WEB_PORT=${STATS_WEB_PORT:-8080}
IDENTITY_PORT=${IDENTITY_PORT:-8013}
FILE_VALIDATION_PORT=${FILE_VALIDATION_PORT:-8014}
DOCUMENT_PARSING_PORT=${DOCUMENT_PARSING_PORT:-8015}
TRANSACTION_EXTRACTION_PORT=${TRANSACTION_EXTRACTION_PORT:-8016}
DATA_VALIDATION_PORT=${DATA_VALIDATION_PORT:-8017}
STATS_DATA_PORT=${STATS_DATA_PORT:-8018}
EMAIL_INGESTION_PORT=${EMAIL_INGESTION_PORT:-8019}
IDENTITY_MODULE_DIR=${IDENTITY_MODULE_DIR:-${STATS_APP_ROOT}/modules/identity-access-module}
FILE_VALIDATION_MODULE_DIR=${FILE_VALIDATION_MODULE_DIR:-${STATS_APP_ROOT}/modules/file-validation-module}
DOCUMENT_PARSING_MODULE_DIR=${DOCUMENT_PARSING_MODULE_DIR:-${STATS_APP_ROOT}/modules/document-parsing-module}
TRANSACTION_EXTRACTION_MODULE_DIR=${TRANSACTION_EXTRACTION_MODULE_DIR:-${STATS_APP_ROOT}/modules/transaction-extraction-module}
DATA_VALIDATION_MODULE_DIR=${DATA_VALIDATION_MODULE_DIR:-${STATS_APP_ROOT}/modules/data-validation-module}
EMAIL_INGESTION_MODULE_DIR=${EMAIL_INGESTION_MODULE_DIR:-${STATS_APP_ROOT}/modules/email-ingestion-module}
STATS_DATA_DIR=${STATS_DATA_DIR:-${STATS_APP_ROOT}/apps/stats-data}
STATS_DATA_SRC_DIR=${STATS_DATA_SRC_DIR:-${STATS_DATA_DIR}/src}
STATS_WEB_DIR=${STATS_WEB_DIR:-${STATS_APP_ROOT}/stats-web}
STATS_DATA_MIGRATIONS_DIR=${STATS_DATA_MIGRATIONS_DIR:-${STATS_DATA_DIR}/migrations/azure-sql}

# database readiness settings
DATABASE_PROVIDER=${DATABASE_PROVIDER:-AzureSql}
AZURE_SQL_CONNECTIONSTRING=${AZURE_SQL_CONNECTIONSTRING:-}

is_container_test_mode() {
    [ "$(echo "${CONTAINER_TEST_MODE}" | tr '[:upper:]' '[:lower:]')" = "true" ]
}

# -- Helpers ------------------------------------------------------------------
wait_for_health() {
    local name="$1"
    local url="$2"
    local elapsed=0

    echo "[M13] Waiting for ${name} at ${url} ..."
    while [ "${elapsed}" -lt "${HEALTH_TIMEOUT}" ]; do
        if curl -sf "${url}" > /dev/null 2>&1; then
            echo "[M13] ${name} is healthy."
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "[M13] ERROR: ${name} did not become healthy within ${HEALTH_TIMEOUT}s. Aborting."
    exit 1
}

wait_for_azure_sql() {
    local elapsed=0
    local probe_timeout=8
    echo "[M13] Waiting for Azure SQL connectivity ..."
    while [ "${elapsed}" -lt "${HEALTH_TIMEOUT}" ]; do
        if AZURE_SQL_CONNECTIONSTRING="${AZURE_SQL_CONNECTIONSTRING}" timeout "${probe_timeout}s" python3 -c "
import os, sys, pyodbc
connection_string = os.environ.get('AZURE_SQL_CONNECTIONSTRING', '')
if not connection_string:
    sys.exit(1)
if 'Driver=' not in connection_string:
    connection_string = 'Driver={ODBC Driver 18 for SQL Server};' + connection_string
connection_string = (
    connection_string
    .replace('Initial Catalog=', 'Database=')
    .replace('User ID=', 'UID=')
    .replace('Password=', 'PWD=')
    .replace('Encrypt=True', 'Encrypt=yes')
    .replace('Encrypt=False', 'Encrypt=no')
    .replace('TrustServerCertificate=True', 'TrustServerCertificate=yes')
    .replace('TrustServerCertificate=False', 'TrustServerCertificate=no')
)
try:
    connection = pyodbc.connect(connection_string, timeout=5)
    connection.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            echo "[M13] Azure SQL is reachable."
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + probe_timeout + 1))
    done

    echo "[M13] ERROR: Azure SQL did not become reachable within ${HEALTH_TIMEOUT}s."
    return 1
}

wait_for_database() {
    if [ "$(echo "${DATABASE_PROVIDER}" | tr '[:upper:]' '[:lower:]')" != "azuresql" ]; then
        echo "[M13] ERROR: DATABASE_PROVIDER must be AzureSql for the active Stats runtime."
        return 1
    fi
    wait_for_azure_sql
}

start_startup_diagnostic() {
    echo "[M13] Starting startup diagnostic page on port ${STATS_WEB_PORT}."
    STARTUP_DIAGNOSTIC_PORT="${STATS_WEB_PORT}" python3 - <<'PY'
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

port = int(os.environ.get("STARTUP_DIAGNOSTIC_PORT", "8080"))
message = "Stats runtime is waiting for Azure SQL connectivity before it can start the cloud-aligned services."

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            body = json.dumps({
                "status": "unhealthy",
                "service": "Stats Runtime",
                "reason": "azure_sql_unreachable",
            }).encode("utf-8")
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stats Runtime Startup</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f7f5; color: #202124; }}
    main {{ max-width: 760px; margin: 12vh auto; padding: 32px; }}
    h1 {{ font-size: 28px; margin: 0 0 16px; }}
    p {{ font-size: 16px; line-height: 1.55; }}
    code {{ background: #ececea; padding: 2px 5px; border-radius: 4px; }}
  </style>
</head>
<body>
  <main>
    <h1>Stats runtime is still starting</h1>
    <p>{message}</p>
    <p>This local container is using the same Azure SQL-backed profile as cloud. Check that this machine can reach <code>sql-stats-dev-001.database.windows.net:1433</code>, then restart the container.</p>
  </main>
</body>
</html>""".encode("utf-8")
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
PY
}

# -- Step 1: Wait for database ------------------------------------------------
if is_container_test_mode; then
    echo "[M13] Container test mode enabled: skipping Azure SQL startup gate and Stats Data persistence startup."
    mkdir -p /app/data
elif ! wait_for_database; then
    if [ "$(echo "${STARTUP_DIAGNOSTIC_ON_FAILURE}" | tr '[:upper:]' '[:lower:]')" = "true" ]; then
        start_startup_diagnostic
    fi
    exit 1
fi

# -- Step 2: Stats Data migrations -------------------------------------------
if ! is_container_test_mode; then
    echo "[M9] Applying Stats Data Azure SQL migrations ..."
    cd "${STATS_DATA_DIR}"
    STATS_DATA_MIGRATIONS_DIR="${STATS_DATA_MIGRATIONS_DIR}" \
        python3 scripts/apply_azure_sql_migrations.py
fi

# -- Step 3: Identity DB init -------------------------------------------------
echo "[M13] Initialising Identity database ..."
cd "${IDENTITY_MODULE_DIR}"
python3 -c "from app.db import init_db; init_db(); print('[M13] Identity DB init complete.')"

# -- Step 4: Start module APIs ------------------------------------------------
echo "[M13] Starting Identity Access API on port ${IDENTITY_PORT} ..."
cd "${IDENTITY_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${IDENTITY_PORT} \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${IDENTITY_PORT}" &

echo "[M13] Starting File Validation API on port ${FILE_VALIDATION_PORT} ..."
cd "${FILE_VALIDATION_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${FILE_VALIDATION_PORT} \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${FILE_VALIDATION_PORT}" &

echo "[M13] Starting Document Parsing API on port ${DOCUMENT_PARSING_PORT} ..."
cd "${DOCUMENT_PARSING_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${DOCUMENT_PARSING_PORT} \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${DOCUMENT_PARSING_PORT}" &

echo "[M13] Starting Transaction Extraction API on port ${TRANSACTION_EXTRACTION_PORT} ..."
cd "${TRANSACTION_EXTRACTION_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${TRANSACTION_EXTRACTION_PORT} \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${TRANSACTION_EXTRACTION_PORT}" &

echo "[M13] Starting Data Validation API on port ${DATA_VALIDATION_PORT} ..."
cd "${DATA_VALIDATION_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${DATA_VALIDATION_PORT} \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${DATA_VALIDATION_PORT}" &

if ! is_container_test_mode; then
    echo "[M9] Starting Stats Data API on port ${STATS_DATA_PORT} ..."
    cd "${STATS_DATA_SRC_DIR}"
    API_HOST=0.0.0.0 API_PORT=${STATS_DATA_PORT} \
        python3 -m uvicorn stats_data.main:app --host 0.0.0.0 --port "${STATS_DATA_PORT}" &
fi

echo "[M12] Starting Email Ingestion API on port ${EMAIL_INGESTION_PORT} ..."
cd "${EMAIL_INGESTION_MODULE_DIR}"
API_HOST=0.0.0.0 API_PORT=${EMAIL_INGESTION_PORT} FILE_INGESTION_BASE_URL="http://localhost:${FILE_VALIDATION_PORT}" \
    DOCUMENT_PARSING_BASE_URL="http://localhost:${DOCUMENT_PARSING_PORT}" \
    TRANSACTION_EXTRACTION_BASE_URL="http://localhost:${TRANSACTION_EXTRACTION_PORT}" \
    DATA_VALIDATION_BASE_URL="http://localhost:${DATA_VALIDATION_PORT}" \
    STATS_DATA_BASE_URL="http://localhost:${STATS_DATA_PORT}" \
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port "${EMAIL_INGESTION_PORT}" &

# -- Step 5: Wait for module API health ---------------------------------------
wait_for_health "Identity Access API"   "http://localhost:${IDENTITY_PORT}/health"
wait_for_health "File Validation API"   "http://localhost:${FILE_VALIDATION_PORT}/health"
wait_for_health "Document Parsing API"  "http://localhost:${DOCUMENT_PARSING_PORT}/health"
wait_for_health "Transaction Extraction API" "http://localhost:${TRANSACTION_EXTRACTION_PORT}/health"
wait_for_health "Data Validation API" "http://localhost:${DATA_VALIDATION_PORT}/health"
if ! is_container_test_mode; then
    wait_for_health "Stats Data API" "http://localhost:${STATS_DATA_PORT}/health"
fi
wait_for_health "Email Ingestion API" "http://localhost:${EMAIL_INGESTION_PORT}/health"

# -- Step 6: Start Stats Web --------------------------------------------------
echo "[M13] All module APIs healthy. Starting Stats Web on port ${STATS_WEB_PORT} ..."
cd "${STATS_WEB_DIR}"
exec dotnet stats.Web.dll \
    --urls "http://0.0.0.0:${STATS_WEB_PORT}" \
    --StatsApi:BaseUrl "" \
    --StatsWeb:Downstream:FileValidationBaseUrl "" \
    --StatsWeb:Downstream:FileIngestionBaseUrl "" \
    --StatsWeb:Downstream:DocumentParsingBaseUrl "" \
    --StatsWeb:Downstream:TransactionExtractionBaseUrl "" \
    --StatsWeb:Downstream:DataValidationBaseUrl "" \
    --StatsWeb:Downstream:EmailIngestionBaseUrl "" \
    --StatsWeb:Downstream:StatsDataBaseUrl "" \
    --StatsWeb:Proxy:IdentityBaseUrl "http://localhost:${IDENTITY_PORT}" \
    --StatsWeb:Proxy:FileValidationBaseUrl "http://localhost:${FILE_VALIDATION_PORT}" \
    --StatsWeb:Proxy:FileIngestionBaseUrl "http://localhost:${FILE_VALIDATION_PORT}" \
    --StatsWeb:Proxy:DocumentParsingBaseUrl "http://localhost:${DOCUMENT_PARSING_PORT}" \
    --StatsWeb:Proxy:TransactionExtractionBaseUrl "http://localhost:${TRANSACTION_EXTRACTION_PORT}" \
    --StatsWeb:Proxy:DataValidationBaseUrl "http://localhost:${DATA_VALIDATION_PORT}" \
    --StatsWeb:Proxy:StatsDataBaseUrl "http://localhost:${STATS_DATA_PORT}" \
    --StatsWeb:Proxy:EmailIngestionBaseUrl "http://localhost:${EMAIL_INGESTION_PORT}"

# M13 End
