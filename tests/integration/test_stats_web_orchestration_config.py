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
DOCUMENTS_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "documents.js"
APP_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "app.js"
CLASSIFICATIONS_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "classifications.js"
ACCESS_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "access.js"
REPORTING_JS_FILE = STATS_WEB_ROOT / "wwwroot" / "js" / "reporting.js"
DOCUMENTS_PAGE_FILE = STATS_WEB_ROOT / "Pages" / "Documents.cshtml"
CLASSIFICATIONS_PAGE_FILE = STATS_WEB_ROOT / "Pages" / "Admin" / "Classifications.cshtml"
CLASSIFICATIONS_MODEL_FILE = STATS_WEB_ROOT / "Pages" / "Admin" / "Classifications.cshtml.cs"
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
    assert appsettings["StatsWeb"]["InternalApiKey"] == ""
    assert downstream["FileValidationBaseUrl"] == ""
    assert downstream["FileIngestionBaseUrl"] == ""
    assert downstream["DocumentParsingBaseUrl"] == ""
    # M13 End
    # M7 - Transaction Extraction Start
    assert downstream["TransactionExtractionBaseUrl"] == ""
    # M7 End
    # M8 - Data Validation Module Start
    assert downstream["DataValidationBaseUrl"] == ""
    assert downstream["StatsDataBaseUrl"] == ""
    # M8 End


def test_stats_web_program_allows_container_environment_overrides():
    """Ensure the container can override downstream URLs through environment variables."""
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")
    classifications_model_source = CLASSIFICATIONS_MODEL_FILE.read_text(encoding="utf-8")

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
    assert "StatsWeb:Downstream:StatsDataBaseUrl" in program_source
    assert "STATS_INTERNAL_API_KEY" in program_source
    assert "X-Stats-Internal-Key" in classifications_model_source


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
    assert "STATS_DATA_PORT" in program_source


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
    assert 'fetch("/api/v1/upload-processing-jobs"' in upload_source
    assert 'fetch(`/api/v1/upload-processing-jobs/${encodeURIComponent(jobId)}`' in upload_source
    assert 'statsApiUrl(documentParsingBaseUrl, "/api/v1/parses")' not in upload_source
    assert 'statsApiUrl(transactionExtractionBaseUrl, "/api/v1/extractions")' in upload_source
    assert 'statsApiUrl(dataValidationBaseUrl, "/api/v1/validations")' in upload_source
    assert 'statsApiUrl(statsDataBaseUrl, "/api/v1/transactions/batches")' in upload_source
    assert 'statsApiUrl(statsDataBaseUrl, "/api/v1/transactions/duplicate-checks")' in upload_source
    assert "buildSaveValidationResult" in upload_source
    assert "checkDuplicateTransactions" in upload_source
    assert "duplicateCheckMessage" in upload_source
    assert "renderDuplicateCheckPanel" in upload_source
    assert "Duplicate save blocked" in upload_source
    assert "Transaction already saved" in upload_source
    assert "downstreamErrorMessage" in upload_source
    assert "ingestionFailureMessage" in upload_source
    assert "Document upload stopped at ingestion. Status:" in upload_source
    assert "finding.message" in upload_source
    assert "resetUploadPage" in upload_source
    assert "Document processing could not be started." in upload_source
    assert "Transactions saved. Choose another file to continue." in upload_source
    assert "transactionTypeOptions" in upload_source
    assert "transactionSubtypeOptions" in upload_source
    assert "spendingCategoryOptions" in upload_source
    assert "spendingSubcategoryOptions" in upload_source
    assert "[\"transaction_type\", \"Transaction type\", \"select\", transactionTypeOptions]" in upload_source
    assert "[\"transaction_subtype\", \"Transaction subtype\", \"select\", transactionSubtypeOptions]" in upload_source
    assert "[\"spending_category\", \"Spending category\", \"select\", spendingCategoryOptions]" in upload_source
    assert "[\"spending_subcategory\", \"Spending subcategory\", \"select\", spendingSubcategoryOptions]" in upload_source
    assert 'category: record.spending_category && record.spending_category !== "uncategorized"' in upload_source
    assert "review-item-header" in upload_source
    assert "review-details review-details-transaction" in upload_source
    assert "[\"Direction\", titleCaseLabel(record.direction || \"unknown\")]" in upload_source


def test_stats_web_upload_uses_async_processing_job_for_cloud_safe_parsing():
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")

    assert "StatsUploadProcessingJobs.StartUploadProcessingJobAsync" in program_source
    assert "StatsUploadProcessingJobs.GetUploadProcessingJobAsync" in program_source
    assert "RunProcessingJobAsync" in program_source
    assert "TimeSpan.FromMinutes(30)" in program_source
    assert '"/api/v1/upload-processing-jobs"' in program_source
    assert '"/api/v1/upload-processing-jobs/{jobId}"' in program_source
    assert "startAcceptedFileProcessingJob" in upload_source
    assert "pollProcessingJob" in upload_source
    assert "renderProcessingJobProgress" in upload_source
    assert "payload.validation_result" in upload_source


def test_upload_duplicate_ingestion_stops_before_async_m5_m7_processing():
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")
    start = upload_source.index("async function sendAcceptedFileToProcessing()")
    end = upload_source.index("async function startAcceptedFileProcessingJob(record)")
    function_source = upload_source[start:end]

    assert 'if (record.status === "queued" && ingestionHandoffReady(record))' in function_source
    assert 'record.status === "queued" || record.status === "duplicate"' not in function_source
    assert 'record.status === "duplicate" ? "Document already uploaded" : "Document upload needs review"' in upload_source
    assert "This document was already uploaded." in upload_source
    assert "function ingestionHandoffReady(record)" in upload_source
    assert "record?.handoff?.content_reference" in upload_source

    queued_start = function_source.index('if (record.status === "queued" && ingestionHandoffReady(record))')
    terminal_start = function_source.index('renderProcessingProgress(1, "Document upload stopped"')
    queued_branch = function_source[queued_start:terminal_start]
    terminal_branch = function_source[terminal_start:]

    assert "await startAcceptedFileProcessingJob(record);" in queued_branch
    assert "await startAcceptedFileProcessingJob(record);" not in terminal_branch
    assert 'setValidationState(ingestionFailureMessage(record), "error");' in terminal_branch
    assert "The queued record did not include a processing handoff." in upload_source


def test_queued_ingestion_still_reaches_m7_extraction_after_m5_parse():
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")

    upload_start = upload_source.index("async function sendAcceptedFileToProcessing()")
    upload_end = upload_source.index("async function startAcceptedFileProcessingJob(record)")
    upload_function = upload_source[upload_start:upload_end]
    queued_start = upload_function.index('if (record.status === "queued" && ingestionHandoffReady(record))')
    terminal_start = upload_function.index('renderProcessingProgress(1, "Document upload stopped"')
    queued_branch = upload_function[queued_start:terminal_start]

    assert "await startAcceptedFileProcessingJob(record);" in queued_branch
    assert 'fetch("/api/v1/upload-processing-jobs"' in upload_source

    parse_step = program_source.index('"document_parsing"')
    extraction_step = program_source.index('"transaction_extraction"')
    validation_step = program_source.index('"data_validation"')
    assert parse_step < extraction_step < validation_step
    assert '/api/v1/extractions' in program_source
    assert "BuildExtractionRequest(parseResult)" in program_source


def test_upload_js_does_not_force_single_page_parse_in_async_flow():
    """Ensure async browser processing preserves statement page coverage."""
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert 'formData.append("allow_ocr_fallback", "true");' in upload_source
    assert 'formData.append("page_limit", "1");' not in upload_source
    assert 'PageLimit: FormValue(form, "page_limit")' in program_source
    assert 'PageLimit: FormValue(form, "page_limit") ?? "1"' not in program_source
    assert 'AddForm(form, "page_limit", metadata.PageLimit);' in program_source
    assert 'formData.append("classification_threshold", "0.1");' in upload_source


def test_stats_web_persists_upload_processing_step_timing():
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "RunTimedStepAsync" in program_source
    assert "AppendProcessingStepAsync" in program_source
    assert "/api/v1/processing-jobs/{WebUtility.UrlEncode(jobId)}/steps" in program_source
    assert '"document_upload"' in program_source
    assert '"document_parsing"' in program_source
    assert '"transaction_extraction"' in program_source
    assert '"data_validation"' in program_source
    assert "duration_ms={DurationMs}" in program_source
    assert "Stopwatch.StartNew()" in program_source
    assert "failed and the failure status could not be persisted" in program_source
    assert "Failed to record initial upload processing step" in program_source
    assert program_source.index("Failed to record initial upload processing step") > program_source.index("TryDeleteTempFile(tempPath);")


def test_upload_reconciliation_respects_explicit_zero_credit_total():
    upload_source = UPLOAD_JS_FILE.read_text(encoding="utf-8")

    assert 'Object.prototype.hasOwnProperty.call(reconciliation, "credit_total")' in upload_source
    assert "const effectiveCreditTotal = hasStatementCreditTotal ? statementCreditTotal : creditTotal;" in upload_source
    assert "statementCreditTotal > 0 ? statementCreditTotal : creditTotal" not in upload_source


def test_documents_page_lists_and_removes_stats_data_records():
    documents_page = DOCUMENTS_PAGE_FILE.read_text(encoding="utf-8")
    documents_source = DOCUMENTS_JS_FILE.read_text(encoding="utf-8")

    assert "/js/documents.js" in documents_page
    assert 'data-stats-data-base-url="@Model.StatsDataBaseUrl"' in documents_page
    assert 'id="documents-table-body"' in documents_page
    assert 'fetch(documentsApiUrl("/api/v1/documents?limit=25")' in documents_source
    assert 'method: "DELETE"' in documents_source
    assert "/api/v1/documents/${encodeURIComponent(documentRecord.document_id)}" in documents_source
    assert "showRemoveConfirmation" in documents_source
    assert 'confirmButton.textContent = "Confirm"' in documents_source
    assert 'cancelButton.textContent = "Cancel"' in documents_source


def test_classification_admin_page_uses_product_language_and_management_sections():
    page_source = CLASSIFICATIONS_PAGE_FILE.read_text(encoding="utf-8")
    model_source = CLASSIFICATIONS_MODEL_FILE.read_text(encoding="utf-8")
    script_source = CLASSIFICATIONS_JS_FILE.read_text(encoding="utf-8")
    app_source = APP_JS_FILE.read_text(encoding="utf-8")

    assert '@page' in page_source
    assert 'href="/Admin/Classifications"' in page_source
    assert "Document types" in page_source
    assert "Transaction labels" in page_source
    assert "Items to review" in page_source
    assert "How Stats recognizes documents" in page_source
    assert "How to use this page" in page_source
    assert "<details class=\"classification-help\">" in page_source
    assert '<div class="classification-stack">' in page_source
    assert 'data-classification-section="document-rules"' in page_source
    assert "Rules Stats uses for documents" in page_source
    assert "Text Stats looks for" in page_source
    assert "Manage transaction labels" in page_source
    assert "Manage spending labels" in page_source
    assert 'asp-page-handler="SaveDocumentLabel"' in page_source
    assert 'asp-page-handler="SaveTransactionLabel"' in page_source
    assert 'asp-page-handler="SaveSpendingLabel"' in page_source
    assert 'asp-page-handler="DeleteDocumentLabel"' in page_source
    assert 'asp-page-handler="DeleteDocumentRule"' in page_source
    assert 'asp-page-handler="DeleteTransactionLabel"' in page_source
    assert 'asp-page-handler="DeleteSpendingLabel"' in page_source
    assert "Delete this document type?" in page_source
    assert "Delete this recognition rule?" in page_source
    assert "Delete this transaction label?" in page_source
    assert "Delete this spending label?" in page_source
    assert "New document type" in page_source
    assert "New transaction type" in page_source
    assert "New spending category" in page_source
    assert "Allowed document examples" in page_source
    assert "Allowed subtypes" in page_source
    assert "Allowed subcategories" in page_source
    assert "classification-management\" open" not in page_source
    assert 'data-async-classification-form data-classification-section="document"' in page_source
    assert 'data-async-classification-form data-classification-section="transaction"' in page_source
    assert 'data-async-classification-form data-classification-section="spending"' in page_source
    assert "Score" not in page_source
    assert "low-confidence" not in page_source.lower()
    assert "M5 Document Parsing" not in page_source
    assert "M7 Transaction Extraction" not in page_source
    assert "M11 boundary" not in page_source
    assert "Read-only" not in page_source
    assert "AI help" not in page_source
    assert "<dt>Provider</dt>" not in page_source
    assert "<dt>Model</dt>" not in page_source
    assert "<dt>Version</dt>" not in page_source
    assert "document-classification.vocabulary.json" in model_source
    assert "document-classification.rules.json" in model_source
    assert "transaction-classification.vocabulary.json" in model_source
    assert "spending-category.rules.json" in model_source
    assert "OnPostSaveDocumentLabelAsync" in model_source
    assert "OnPostDeleteDocumentLabelAsync" in model_source
    assert "OnPostDeleteDocumentRuleAsync" in model_source
    assert "OnPostDeleteTransactionLabelAsync" in model_source
    assert "OnPostDeleteSpendingLabelAsync" in model_source
    assert "SaveDocumentLabel(" in model_source
    assert "DeleteDocumentLabel(" in model_source
    assert "DeleteTransactionLabel(" in model_source
    assert "DeleteSpendingLabel(" in model_source
    assert "The Unknown fallback label cannot be deleted." in model_source
    assert "CLASSIFICATION_AI_ENABLED" not in model_source
    assert "CLASSIFICATION_AI_MODEL_VERSION" not in model_source
    assert "Stats Web /Admin/Classifications" not in model_source
    assert "user.role !== \"admin\"" in script_source
    assert "Administrator access is required." in script_source
    assert "data-classification-tab" in script_source
    assert "saveClassificationForm" in script_source
    assert "refreshWorkbench" in script_source
    assert "\"X-Stats-Async-Save\": \"true\"" in script_source
    assert "event.preventDefault()" in script_source
    assert "window.confirm(form.dataset.confirmMessage)" in script_source
    assert "read-only classification" not in script_source
    assert "data-admin-link" in app_source
    assert "user.role !== \"admin\"" in app_source


def test_admin_navigation_is_client_revealed_after_identity_check():
    page_files = [
        STATS_WEB_ROOT / "Pages" / "Index.cshtml",
        STATS_WEB_ROOT / "Pages" / "Upload.cshtml",
        STATS_WEB_ROOT / "Pages" / "Documents.cshtml",
        STATS_WEB_ROOT / "Pages" / "Reports.cshtml",
        STATS_WEB_ROOT / "Pages" / "EmailSetup.cshtml",
    ]
    model_files = [
        STATS_WEB_ROOT / "Pages" / "Index.cshtml.cs",
        STATS_WEB_ROOT / "Pages" / "Upload.cshtml.cs",
        STATS_WEB_ROOT / "Pages" / "Documents.cshtml.cs",
        STATS_WEB_ROOT / "Pages" / "Reports.cshtml.cs",
        STATS_WEB_ROOT / "Pages" / "EmailSetup.cshtml.cs",
    ]

    for page_file in page_files:
        source = page_file.read_text(encoding="utf-8")
        if page_file.name != "Index.cshtml":
            assert "@if (Model.IsAdmin)" not in source
        assert 'data-admin-link href="/Users" hidden>Manage users' in source
        assert 'data-admin-link href="/Admin/Classifications" hidden>Recognition settings' in source
        assert "Recognition settings" in source

    for model_file in model_files:
        source = model_file.read_text(encoding="utf-8")
        assert "StatsUserContextService" in source
        assert "IsAdmin" in source
        assert "IsAdminAsync(HttpContext)" in source


def test_access_helper_mirrors_session_token_for_server_form_posts():
    access_source = ACCESS_JS_FILE.read_text(encoding="utf-8")
    page_sources = [
        (STATS_WEB_ROOT / "Pages" / "Login.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "Index.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "Upload.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "Documents.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "Reports.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "EmailSetup.cshtml").read_text(encoding="utf-8"),
        (STATS_WEB_ROOT / "Pages" / "Users.cshtml").read_text(encoding="utf-8"),
        CLASSIFICATIONS_PAGE_FILE.read_text(encoding="utf-8"),
    ]

    assert "tokenCookieName: \"stats_access_token\"" in access_source
    assert "setTokenCookie(token)" in access_source
    assert "cookieToken()" in access_source
    assert "sessionStorage.setItem(this.tokenKey, cookieToken)" in access_source
    assert "this.setTokenCookie(token);" in access_source
    for source in page_sources:
        assert 'src="/js/access.js" defer asp-append-version="true"' in source


def test_reporting_js_does_not_show_raw_powerbi_error_details():
    reporting_source = REPORTING_JS_FILE.read_text(encoding="utf-8")

    assert "safeReportingErrorMessage" in reporting_source
    assert 'setReportingStatus("unavailable", safeReportingErrorMessage())' in reporting_source
    assert 'setReportingStatus("unavailable", message)' not in reporting_source


def test_reporting_endpoints_require_server_side_user_context():
    program_source = PROGRAM_FILE.read_text(encoding="utf-8")

    assert "StatsReportingKpis.GetKpisAsync" in program_source
    assert "StatsReportingEmbedConfig.GetEmbedConfigAsync" in program_source
    assert "StatsUserContextService userContext" in program_source
    assert "await userContext.GetCurrentUserAsync(context)" in program_source
    assert "return Results.Unauthorized();" in program_source
    assert "return Results.StatusCode(StatusCodes.Status403Forbidden);" in program_source
    assert "or JsonException" in program_source


def test_home_financial_kpis_are_admin_only():
    page_source = (STATS_WEB_ROOT / "Pages" / "Index.cshtml").read_text(encoding="utf-8")

    assert "@if (Model.IsAdmin)" in page_source
    assert page_source.index("@if (Model.IsAdmin)") < page_source.index("data-kpi-card")
    assert "data-kpi-card" in page_source
    assert 'id="reporting-currency"' in page_source
