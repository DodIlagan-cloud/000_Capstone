# M9 - Stats Data and Persistence Start
# Verifies the Azure SQL migration/config contract without live credentials.

import json
from pathlib import Path


REPO_ROOT = Path(__file__).parent.parent.parent
MIGRATION = (
    REPO_ROOT
    / "apps"
    / "stats-data"
    / "migrations"
    / "azure-sql"
    / "001_initial_stats_data_schema.sql"
)
MIGRATION_2 = (
    REPO_ROOT
    / "apps"
    / "stats-data"
    / "migrations"
    / "azure-sql"
    / "002_validation_reporting_schema.sql"
)
MIGRATION_5 = (
    REPO_ROOT
    / "apps"
    / "stats-data"
    / "migrations"
    / "azure-sql"
    / "005_duplicate_check_results.sql"
)
MIGRATION_6 = (
    REPO_ROOT
    / "apps"
    / "stats-data"
    / "migrations"
    / "azure-sql"
    / "006_document_processing_jobs.sql"
)
MIGRATION_7 = (
    REPO_ROOT
    / "apps"
    / "stats-data"
    / "migrations"
    / "azure-sql"
    / "007_document_processing_steps.sql"
)
MIGRATION_README = REPO_ROOT / "apps" / "stats-data" / "migrations" / "azure-sql" / "README.md"
M9_SPEC = REPO_ROOT / "docs" / "M9-stats-data-persistence-module-spec.md"
M9_ERD = REPO_ROOT / "docs" / "M9-stats-data-erd.md"
M9_FILE_INVENTORY = REPO_ROOT / "docs" / "M9-stats-data-file-inventory.md"
CLOUD_SQL_EVIDENCE = REPO_ROOT / "infrastructure" / "cloud" / "cloud-dev-azure-sql-evidence.md"
CLOUD_ENV_EXAMPLE = REPO_ROOT / "infrastructure" / "cloud" / "azure-container-apps.env.example"
RUNTIME_CONFIG = REPO_ROOT / "config" / "stats.runtime.json"
IDENTITY_CONFIG = REPO_ROOT / "modules" / "identity-access-module" / "app" / "config.py"
IDENTITY_DB = REPO_ROOT / "modules" / "identity-access-module" / "app" / "db.py"
IDENTITY_REQUIREMENTS = REPO_ROOT / "modules" / "identity-access-module" / "requirements.txt"
IDENTITY_DEFAULTS = REPO_ROOT / "modules" / "identity-access-module" / "config" / "defaults.env"
STARTUP_SCRIPT = REPO_ROOT / "infrastructure" / "containers" / "stats" / "start-stats-runtime.sh"
COMPOSE_FILE = REPO_ROOT / "infrastructure" / "compose" / "stats-runtime.compose.yml"
DOCKERFILE = REPO_ROOT / "infrastructure" / "containers" / "stats" / "Dockerfile"
MIGRATION_RUNNER = REPO_ROOT / "apps" / "stats-data" / "scripts" / "apply_azure_sql_migrations.py"
VALIDATION_PERSISTENCE_ADAPTER = REPO_ROOT / "apps" / "stats-data" / "src" / "stats_data" / "validation_persistence.py"
STATS_DATA_API = REPO_ROOT / "apps" / "stats-data" / "src" / "stats_data" / "api.py"
STATS_DATA_DATABASE = REPO_ROOT / "apps" / "stats-data" / "src" / "stats_data" / "database.py"
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
M13_EVIDENCE_RUNNER = REPO_ROOT / "tests" / "scripts" / "M13-Containerization" / "run_docker_acceptance_evidence.ps1"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_m9_azure_sql_assets_exist():
    for path in [
        MIGRATION,
        MIGRATION_2,
        MIGRATION_5,
        MIGRATION_6,
        MIGRATION_7,
        MIGRATION_README,
        M9_SPEC,
        M9_ERD,
        M9_FILE_INVENTORY,
        CLOUD_SQL_EVIDENCE,
        IDENTITY_CONFIG,
        IDENTITY_DB,
        STARTUP_SCRIPT,
        COMPOSE_FILE,
        MIGRATION_RUNNER,
        VALIDATION_PERSISTENCE_ADAPTER,
        DOCKERIGNORE,
        M13_EVIDENCE_RUNNER,
    ]:
        assert path.exists(), f"Expected M9 Azure SQL asset at {path}"


def test_migration_uses_azure_sql_types_and_migration_tracking():
    content = read(MIGRATION)
    required_terms = [
        "CREATE TABLE dbo.schema_migrations",
        "SYSUTCDATETIME()",
        "datetime2(3)",
        "nvarchar",
        "decimal(19,4)",
        "bit",
        "ISJSON",
        "GO",
        "001_initial_stats_data_schema",
    ]
    for term in required_terms:
        assert term in content, f"Migration must include Azure SQL term {term}"
    assert "document_fingerprint nvarchar(64) NULL" in content


def test_migration_creates_required_m9_tables():
    content = f"{read(MIGRATION)}\n{read(MIGRATION_2)}\n{read(MIGRATION_5)}\n{read(MIGRATION_6)}\n{read(MIGRATION_7)}".lower()
    required_tables = [
        "dbo.validation_results",
        "dbo.stats_documents",
        "dbo.processing_runs",
        "dbo.transaction_batches",
        "dbo.transactions",
        "dbo.financial_fields",
        "dbo.document_sections",
        "dbo.statement_summaries",
        "dbo.document_financial_summaries",
        "dbo.line_items",
        "dbo.validated_entities",
        "dbo.validated_references",
        "dbo.installments",
        "dbo.financial_evidence_links",
        "dbo.findings",
        "dbo.review_items",
        "dbo.duplicate_check_batches",
        "dbo.duplicate_check_results",
        "dbo.document_processing_jobs",
        "dbo.document_processing_steps",
    ]
    for table in required_tables:
        assert table in content, f"Migration must create or reference {table}"


def test_migration_avoids_postgresql_only_syntax():
    content = f"{read(MIGRATION)}\n{read(MIGRATION_2)}\n{read(MIGRATION_5)}\n{read(MIGRATION_6)}\n{read(MIGRATION_7)}".lower()
    forbidden_terms = [
        " jsonb",
        " uuid",
        " serial",
        " bigserial",
        " timestamptz",
        " now()",
        " gen_random_uuid",
        " references public.",
    ]
    for term in forbidden_terms:
        assert term not in content, f"Azure SQL migration must not use PostgreSQL-only syntax: {term}"


def test_migration_supports_dashboard_indexes_and_duplicate_key():
    content = f"{read(MIGRATION)}\n{read(MIGRATION_2)}\n{read(MIGRATION_5)}"
    required_terms = [
        "ix_transactions_reporting",
        "ux_transactions_duplicate_key",
        "ix_statement_summaries_due_date",
        "ix_review_items_status_severity",
        "duplicate_key",
    ]
    for term in required_terms:
        assert term in content, f"Migration must support dashboard/duplicate contract term {term}"


def test_validation_reporting_migration_supports_current_validation_contract():
    content = read(MIGRATION_2)
    required_terms = [
        "002_validation_reporting_schema",
        "section_candidate_count",
        "entity_count",
        "reference_count",
        "line_item_count",
        "installment_count",
        "warning_installment_count",
        "invalid_installment_count",
        "CREATE TABLE dbo.document_sections",
        "CREATE TABLE dbo.validated_entities",
        "CREATE TABLE dbo.validated_references",
        "CREATE TABLE dbo.installments",
        "source_section_id",
        "source_section_label",
        "source_ocr_confidence",
        "source_extraction_confidence",
        "reason_codes_json",
        "ck_transactions_reason_codes_json",
        "ck_financial_fields_reason_codes_json",
        "ck_line_items_reason_codes_json",
        "ck_review_items_reason_codes_json",
    ]
    for term in required_terms:
        assert term in content, f"M9 must support evolved validation persistence term {term}"
    normalize_migration_content = "\n".join(
        read(path)
        for path in [
            MIGRATION_2,
            REPO_ROOT / "apps" / "stats-data" / "migrations" / "azure-sql" / "003_normalize_validation_results_schema.sql",
            REPO_ROOT / "apps" / "stats-data" / "migrations" / "azure-sql" / "004_normalize_stats_documents_validation_reference.sql",
        ]
    )
    assert "sp_executesql" not in normalize_migration_content
    assert "EXEC sp_rename N'dbo.m8_validation_results', N'validation_results'" in content


def test_processing_jobs_migration_supports_async_cloud_upload_contract():
    content = read(MIGRATION_6)
    required_terms = [
        "006_document_processing_jobs",
        "CREATE TABLE dbo.document_processing_jobs",
        "job_id",
        "ingestion_id",
        "uploaded_by_user_id",
        "original_filename",
        "status",
        "stage",
        "parse_id",
        "extraction_id",
        "validation_id",
        "result_payload_json",
        "error_detail",
        "ix_document_processing_jobs_user_status",
        "ck_document_processing_jobs_result_json",
    ]
    for term in required_terms:
        assert term in content, f"M9 async processing job migration must include {term}"


def test_processing_steps_migration_supports_upload_timing_contract():
    content = read(MIGRATION_7)
    required_terms = [
        "007_document_processing_steps",
        "CREATE TABLE dbo.document_processing_steps",
        "step_id",
        "job_id",
        "document_id",
        "correlation_id",
        "module_name",
        "step_name",
        "started_at_utc",
        "completed_at_utc",
        "duration_ms",
        "metadata_json",
        "error_code",
        "error_message",
        "fk_document_processing_steps_job",
        "ix_document_processing_steps_job_created",
        "ck_document_processing_steps_metadata_json",
    ]
    for term in required_terms:
        assert term in content, f"M9 processing-step migration must include {term}"


def test_erd_matches_validation_promoted_tables():
    erd = read(M9_ERD)
    required_terms = [
        "DOCUMENT_SECTIONS",
        "VALIDATED_ENTITIES",
        "VALIDATED_REFERENCES",
        "INSTALLMENTS",
        "normalized_description",
        "duplicate_key",
        "reason_codes_json",
        "source_section_id",
        "source_ocr_confidence",
        "M9 persists only validation output",
    ]
    for term in required_terms:
        assert term in erd, f"ERD must document validation-enriched persistence term {term}"


def test_migration_creates_tables_before_foreign_key_dependents():
    content = read(MIGRATION).lower()

    transactions_create = content.index("create table dbo.transactions")
    evidence_links_create = content.index("create table dbo.financial_evidence_links")
    processing_runs_create = content.index("create table dbo.processing_runs")
    findings_create = content.index("create table dbo.findings")

    assert transactions_create < evidence_links_create, (
        "financial_evidence_links must be created after transactions because it "
        "declares transaction foreign keys."
    )
    assert processing_runs_create < findings_create, (
        "findings must be created after processing_runs because it declares a "
        "processing_run_id foreign key."
    )


def test_cloud_env_documents_azure_sql_settings_without_secret_values():
    content = read(CLOUD_ENV_EXAMPLE)
    required_terms = [
        "DATABASE_PROVIDER=AzureSql",
        "DATABASE_SCHEMA=dbo",
        "AZURE_SQL_SERVER=sql-stats-dev-001.database.windows.net",
        "AZURE_SQL_DATABASE=sqldb-stats-dev",
        "AZURE_SQL_CONNECTIONSTRING=secretref:stats-azure-sql-connectionstring",
        "STATS_VALIDATION_HANDOFF_DIR=/app/apps/stats-data/data/validation-handoff",
        "STATS_DATA_PORT=8018",
    ]
    for term in required_terms:
        assert term in content, f"Cloud env example must document {term}"
    assert "Password=" not in content


def test_runtime_config_documents_m9_database_provider_settings():
    config = json.loads(read(RUNTIME_CONFIG))
    database = config["database"]
    storage = config["storage"]
    assert database["DATABASE_PROVIDER"]["default"] == "AzureSql"
    assert database["DATABASE_SCHEMA"]["default"] == "dbo"
    assert database["AZURE_SQL_CONNECTIONSTRING"]["secret"] is True
    assert storage["STATS_VALIDATION_HANDOFF_DIR"]["default"] == "apps/stats-data/data/validation-handoff"
    assert storage["STATS_VALIDATION_HANDOFF_DIR"]["secret"] is False
    assert "DATABASE_URL" not in database
    assert config["cloud"]["AZURE_SQL_SERVER"]["example"] == "sql-stats-dev-001.database.windows.net"
    assert config["cloud"]["AZURE_SQL_DATABASE"]["example"] == "sqldb-stats-dev"
    assert config["modulePorts"]["STATS_DATA_PORT"]["default"] == "8018"


def test_path_map_documents_validation_handoff_directory():
    paths = json.loads(read(REPO_ROOT / "config" / "stats.paths.json"))
    assert paths["storage"]["validationHandoff"] == "apps/stats-data/data/validation-handoff"


def test_evidence_records_secret_names_not_values():
    content = read(CLOUD_SQL_EVIDENCE)
    assert "stats-sql-admin-password" in content
    assert "stats-azure-sql-connectionstring" in content
    forbidden_fragments = ["Password=", "AccountKey=", "SharedAccessSignature=", "statspass"]
    for fragment in forbidden_fragments:
        assert fragment not in content, f"Evidence must not contain secret value fragment {fragment}"


def test_identity_runtime_uses_provider_aware_azure_sql_settings():
    config_source = read(IDENTITY_CONFIG)
    db_source = read(IDENTITY_DB)
    defaults = read(IDENTITY_DEFAULTS)
    requirements = read(IDENTITY_REQUIREMENTS)

    assert "database_provider" in config_source
    assert "AZURE_SQL_CONNECTIONSTRING" in config_source
    assert "DATABASE_PROVIDER=AzureSql" in defaults
    assert "DATABASE_SCHEMA=dbo" in defaults
    assert "AZURE_SQL_CONNECTIONSTRING=" in defaults
    assert "mssql+pyodbc" in db_source
    assert "ODBC Driver 18 for SQL Server" in db_source
    assert "pyodbc" in requirements
    assert "psycopg" not in requirements.lower()


def test_startup_runtime_requires_azure_sql_and_does_not_print_connection_string():
    startup = read(STARTUP_SCRIPT)

    assert "DATABASE_PROVIDER=${DATABASE_PROVIDER:-AzureSql}" in startup
    assert "wait_for_azure_sql" in startup
    assert "STATS_DATA_MIGRATIONS_DIR" in startup
    assert "STATS_DATA_PORT=${STATS_DATA_PORT:-8018}" in startup
    assert "uvicorn stats_data.main:app" in startup
    assert "http://localhost:${STATS_DATA_PORT}/health" in startup
    assert "scripts/apply_azure_sql_migrations.py" in startup
    assert "pyodbc.connect" in startup
    assert "DATABASE_PROVIDER must be AzureSql" in startup
    assert "stats-db" not in startup
    assert "pg_isready" not in startup
    assert "psql" not in startup
    assert "echo ${AZURE_SQL_CONNECTIONSTRING}" not in startup
    assert "print(os.environ" not in startup


def test_compose_uses_azure_sql_runtime_without_postgres_service():
    compose = read(COMPOSE_FILE)

    assert "DATABASE_PROVIDER: \"${DATABASE_PROVIDER:-AzureSql}\"" in compose
    assert "DATABASE_SCHEMA: \"${DATABASE_SCHEMA:-dbo}\"" in compose
    assert (
        "AZURE_SQL_CONNECTIONSTRING: "
        "\"${AZURE_SQL_CONNECTIONSTRING:?Set AZURE_SQL_CONNECTIONSTRING in infrastructure/compose/.env.container}\""
    ) in compose
    assert 'STATS_VALIDATION_HANDOFF_DIR: "${STATS_VALIDATION_HANDOFF_DIR:-/app/apps/stats-data/data/validation-handoff}"' in compose
    assert 'STATS_DATA_PORT: "${STATS_DATA_PORT:-8018}"' in compose
    assert "postgres:" not in compose.lower()
    assert "stats-db:" not in compose
    assert "POSTGRES_PASSWORD" not in compose
    assert "DATABASE_URL" not in compose


def test_dockerfile_includes_azure_sql_driver_dependencies():
    dockerfile = read(DOCKERFILE)

    assert "msodbcsql18" in dockerfile
    assert "unixodbc" in dockerfile
    assert "import pyodbc" in dockerfile
    assert "ENV STATS_VALIDATION_HANDOFF_DIR=/app/apps/stats-data/data/validation-handoff" in dockerfile
    assert "ENV STATS_DATA_PORT=8018" in dockerfile


def test_dockerfile_packages_m9_migrations_without_runtime_intake_data():
    dockerfile = read(DOCKERFILE)
    dockerignore = read(DOCKERIGNORE)

    assert "COPY apps/stats-data/migrations/ /app/apps/stats-data/migrations/" in dockerfile
    assert "COPY apps/stats-data/scripts/ /app/apps/stats-data/scripts/" in dockerfile
    assert "COPY apps/stats-data/src/ /app/apps/stats-data/src/" in dockerfile
    assert "COPY apps/stats-data/ /app/apps/stats-data/" not in dockerfile
    assert "apps/stats-data/data/" in dockerignore


def test_m9_adapter_maps_validation_staging_and_promoted_tables():
    adapter = read(VALIDATION_PERSISTENCE_ADAPTER)
    required_terms = [
        "build_validation_persistence_plan",
        "persist_validation_result",
        "validation_results",
        "stats_documents",
        "transaction_batches",
        "transactions",
        "financial_fields",
        "document_sections",
        "validated_entities",
        "validated_references",
        "line_items",
        "installments",
        "review_items",
        "duplicate_check_batches",
        "duplicate_check_results",
        "payload_json",
        "duplicate_key",
        "document_fingerprint",
    ]
    for term in required_terms:
        assert term in adapter, f"M9 adapter must include {term}"


def test_m9_adapter_uses_temp_validation_payload_handoff_until_success():
    adapter = read(VALIDATION_PERSISTENCE_ADAPTER)
    required_terms = [
        "write_validation_payload_temp_file",
        "load_validation_payload_temp_file",
        "build_validation_persistence_plan_from_temp_file",
        "persist_validation_result_from_temp_file",
        "persist_validation_result_with_temp_handoff",
        "VALIDATION_HANDOFF_DIR_ENV",
        "STATS_VALIDATION_HANDOFF_DIR",
        "handoff_path.unlink()",
        "Could not remove validation handoff file after successful commit",
        "persist_validation_result(connection, load_validation_payload_temp_file",
    ]
    for term in required_terms:
        assert term in adapter, f"M9 adapter must guard temp validation payload handoff term {term}"


def test_m9_stats_data_api_exposes_save_boundary():
    api = read(STATS_DATA_API)
    database = read(STATS_DATA_DATABASE)

    assert '@app.post("/api/v1/transactions/batches"' in api
    assert '@app.post("/api/v1/transactions/duplicate-checks"' in api
    assert '@app.get("/api/v1/documents"' in api
    assert '@app.delete("/api/v1/documents/{document_id}"' in api
    assert "SaveTransactionsBatchRequest" in api
    assert "DuplicateCheckRequest" in api
    assert "check_validation_duplicates" in api
    assert "UploadedDocumentsResponse" in api
    assert "DeleteUploadedDocumentResponse" in api
    assert "list_recent_uploaded_documents" in api
    assert "persist_validation_result_with_temp_handoff" in api
    assert "delete_uploaded_document_records" in api
    assert "uploaded_by_user_id" in api
    assert "saved_by_user_id" in api
    assert "saved_record_count" in api
    assert "AZURE_SQL_CONNECTIONSTRING" in database
    assert "DATABASE_PROVIDER" in database
    assert "pyodbc.connect" in database


def test_official_container_evidence_checks_azure_sql_not_postgres():
    runner = read(M13_EVIDENCE_RUNNER)

    assert "Azure SQL schema check" in runner
    assert "INFORMATION_SCHEMA.TABLES" in runner
    assert "TABLE_SCHEMA='dbo'" in runner
    assert "TABLE_NAME='users'" in runner
    assert "psql" not in runner
    assert "$DbContainer" not in runner
    assert "stats-db" not in runner


def test_m9_migration_runner_uses_azure_sql_without_printing_secrets():
    runner = read(MIGRATION_RUNNER)

    assert "AZURE_SQL_CONNECTIONSTRING" in runner
    assert "DATABASE_PROVIDER" in runner
    assert "AzureSql" in runner
    assert "pyodbc.connect" in runner
    assert "ODBC Driver 18 for SQL Server" in runner
    assert "GO" in runner
    assert "schema_migrations" not in runner, "Migration tracking belongs to SQL scripts, not duplicated in runner logic."
    forbidden_fragments = [
        "print(connection_string",
        "print(os.environ",
        "stats-sql-admin-password",
        "stats-azure-sql-connectionstring",
    ]
    for fragment in forbidden_fragments:
        assert fragment not in runner, f"Migration runner must not print or hardcode secret material: {fragment}"

# M9 End
