#!/bin/bash
# M13 - Containerization Start
# Starts all Stats module APIs in order, waits for health checks, then starts Stats Web.
# Order: database ready -> identity DB init -> Identity API -> File Validation API -> Document Parsing API -> Transaction Extraction API -> Data Validation API -> Stats Web

set -e

# -- Configuration ------------------------------------------------------------
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-60}
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
IDENTITY_MODULE_DIR=${IDENTITY_MODULE_DIR:-${STATS_APP_ROOT}/modules/identity-access-module}
FILE_VALIDATION_MODULE_DIR=${FILE_VALIDATION_MODULE_DIR:-${STATS_APP_ROOT}/modules/file-validation-module}
DOCUMENT_PARSING_MODULE_DIR=${DOCUMENT_PARSING_MODULE_DIR:-${STATS_APP_ROOT}/modules/document-parsing-module}
TRANSACTION_EXTRACTION_MODULE_DIR=${TRANSACTION_EXTRACTION_MODULE_DIR:-${STATS_APP_ROOT}/modules/transaction-extraction-module}
DATA_VALIDATION_MODULE_DIR=${DATA_VALIDATION_MODULE_DIR:-${STATS_APP_ROOT}/modules/data-validation-module}
STATS_WEB_DIR=${STATS_WEB_DIR:-${STATS_APP_ROOT}/stats-web}

# stats-db connection details (used for readiness check)
DB_HOST=${DB_HOST:-stats-db}
DB_PORT=${DB_PORT:-5432}

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

wait_for_database() {
    local elapsed=0
    echo "[M13] Waiting for database at ${DB_HOST}:${DB_PORT} ..."
    while [ "${elapsed}" -lt "${HEALTH_TIMEOUT}" ]; do
        if python3 -c "
import socket, sys
try:
    s = socket.create_connection(('${DB_HOST}', ${DB_PORT}), timeout=2)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            echo "[M13] Database is reachable."
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    echo "[M13] ERROR: Database at ${DB_HOST}:${DB_PORT} did not become reachable within ${HEALTH_TIMEOUT}s. Aborting."
    exit 1
}

# -- Step 1: Wait for database ------------------------------------------------
wait_for_database

# -- Step 2: Identity DB init -------------------------------------------------
echo "[M13] Initialising Identity database ..."
cd "${IDENTITY_MODULE_DIR}"
python3 -c "from app.db import init_db; init_db(); print('[M13] Identity DB init complete.')"

# -- Step 3: Start module APIs ------------------------------------------------
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

# -- Step 4: Wait for module API health ---------------------------------------
wait_for_health "Identity Access API"   "http://localhost:${IDENTITY_PORT}/health"
wait_for_health "File Validation API"   "http://localhost:${FILE_VALIDATION_PORT}/health"
wait_for_health "Document Parsing API"  "http://localhost:${DOCUMENT_PARSING_PORT}/health"
wait_for_health "Transaction Extraction API" "http://localhost:${TRANSACTION_EXTRACTION_PORT}/health"
wait_for_health "Data Validation API" "http://localhost:${DATA_VALIDATION_PORT}/health"

# -- Step 5: Start Stats Web --------------------------------------------------
echo "[M13] All module APIs healthy. Starting Stats Web on port ${STATS_WEB_PORT} ..."
cd "${STATS_WEB_DIR}"
exec dotnet stats.Web.dll \
    --urls "http://0.0.0.0:${STATS_WEB_PORT}" \
    --StatsApi:BaseUrl "" \
    --StatsWeb:Downstream:FileValidationBaseUrl "" \
    --StatsWeb:Downstream:FileIngestionBaseUrl "" \
    --StatsWeb:Downstream:DocumentParsingBaseUrl "" \
    --StatsWeb:Proxy:IdentityBaseUrl "http://localhost:${IDENTITY_PORT}" \
    --StatsWeb:Proxy:FileValidationBaseUrl "http://localhost:${FILE_VALIDATION_PORT}" \
    --StatsWeb:Proxy:FileIngestionBaseUrl "http://localhost:${FILE_VALIDATION_PORT}" \
    --StatsWeb:Proxy:DocumentParsingBaseUrl "http://localhost:${DOCUMENT_PARSING_PORT}" \
    --StatsWeb:Proxy:TransactionExtractionBaseUrl "http://localhost:${TRANSACTION_EXTRACTION_PORT}" \
    --StatsWeb:Proxy:DataValidationBaseUrl "http://localhost:${DATA_VALIDATION_PORT}"

# M13 End
