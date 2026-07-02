#!/bin/bash
# M12 - Email Ingestion Module Start
# Runs one scheduled email ingestion tick from an Azure Container Apps Job.

set -eu

STATS_WEB_BASE_URL=${STATS_WEB_BASE_URL:-}
M12_SCHEDULED_RUN_URL=${M12_SCHEDULED_RUN_URL:-}
STATS_INTERNAL_API_KEY=${STATS_INTERNAL_API_KEY:-}
REQUEST_TIMEOUT_SECONDS=${M12_SCHEDULED_RUN_TIMEOUT_SECONDS:-300}

if [ -z "${M12_SCHEDULED_RUN_URL}" ]; then
    if [ -z "${STATS_WEB_BASE_URL}" ]; then
        echo "[M12] ERROR: STATS_WEB_BASE_URL or M12_SCHEDULED_RUN_URL is required."
        exit 2
    fi
    M12_SCHEDULED_RUN_URL="${STATS_WEB_BASE_URL%/}/api/v1/email-ingestions/scheduled-runs"
fi

if [ -z "${STATS_INTERNAL_API_KEY}" ]; then
    echo "[M12] ERROR: STATS_INTERNAL_API_KEY is required for scheduled email ingestion."
    exit 2
fi

body_file=$(mktemp)
status_file=$(mktemp)
cleanup() {
    rm -f "${body_file}" "${status_file}"
}
trap cleanup EXIT

echo "[M12] Scheduled email ingestion tick starting."
echo "[M12] Target: ${M12_SCHEDULED_RUN_URL}"

http_status=$(
    curl -sS \
        --max-time "${REQUEST_TIMEOUT_SECONDS}" \
        -X POST "${M12_SCHEDULED_RUN_URL}" \
        -H "X-Stats-CSRF: 1" \
        -H "X-Stats-Internal-Key: ${STATS_INTERNAL_API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{}" \
        -o "${body_file}" \
        -w "%{http_code}" \
        2> "${status_file}" || true
)

curl_error=$(cat "${status_file}" || true)
response_body=$(cat "${body_file}" || true)

if [ -n "${curl_error}" ]; then
    echo "[M12] curl output: ${curl_error}"
fi

echo "[M12] HTTP status: ${http_status}"
echo "[M12] Response body: ${response_body}"

case "${http_status}" in
    2*)
        echo "[M12] Scheduled email ingestion tick completed."
        exit 0
        ;;
    *)
        echo "[M12] ERROR: Scheduled email ingestion tick failed."
        exit 1
        ;;
esac

# M12 End
