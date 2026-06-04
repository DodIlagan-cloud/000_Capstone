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


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_m9_azure_sql_assets_exist():
    for path in [
        MIGRATION,
        MIGRATION_README,
        M9_SPEC,
        M9_ERD,
        M9_FILE_INVENTORY,
        CLOUD_SQL_EVIDENCE,
        IDENTITY_CONFIG,
        IDENTITY_DB,
        STARTUP_SCRIPT,
        COMPOSE_FILE,
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


def test_migration_creates_required_m9_tables():
    content = read(MIGRATION).lower()
    required_tables = [
        "dbo.m8_validation_results",
        "dbo.stats_documents",
        "dbo.processing_runs",
        "dbo.transaction_batches",
        "dbo.transactions",
        "dbo.financial_fields",
        "dbo.statement_summaries",
        "dbo.document_financial_summaries",
        "dbo.line_items",
        "dbo.financial_evidence_links",
        "dbo.findings",
        "dbo.review_items",
    ]
    for table in required_tables:
        assert table in content, f"Migration must create or reference {table}"


def test_migration_avoids_postgresql_only_syntax():
    content = read(MIGRATION).lower()
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
    content = read(MIGRATION)
    required_terms = [
        "ix_transactions_reporting",
        "ux_transactions_duplicate_key",
        "ix_statement_summaries_due_date",
        "ix_review_items_status_severity",
        "duplicate_key",
    ]
    for term in required_terms:
        assert term in content, f"Migration must support dashboard/duplicate contract term {term}"


def test_cloud_env_documents_azure_sql_settings_without_secret_values():
    content = read(CLOUD_ENV_EXAMPLE)
    required_terms = [
        "DATABASE_PROVIDER=AzureSql",
        "DATABASE_SCHEMA=dbo",
        "AZURE_SQL_SERVER=sql-stats-dev-001.database.windows.net",
        "AZURE_SQL_DATABASE=sqldb-stats-dev",
        "AZURE_SQL_CONNECTIONSTRING=secretref:stats-azure-sql-connectionstring",
    ]
    for term in required_terms:
        assert term in content, f"Cloud env example must document {term}"
    assert "Password=" not in content


def test_runtime_config_documents_m9_database_provider_settings():
    config = json.loads(read(RUNTIME_CONFIG))
    database = config["database"]
    assert database["DATABASE_PROVIDER"]["default"] == "AzureSql"
    assert database["DATABASE_SCHEMA"]["default"] == "dbo"
    assert database["AZURE_SQL_CONNECTIONSTRING"]["secret"] is True
    assert "DATABASE_URL" not in database
    assert config["cloud"]["AZURE_SQL_SERVER"]["example"] == "sql-stats-dev-001.database.windows.net"
    assert config["cloud"]["AZURE_SQL_DATABASE"]["example"] == "sqldb-stats-dev"


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
    assert "AZURE_SQL_CONNECTIONSTRING: \"${AZURE_SQL_CONNECTIONSTRING}\"" in compose
    assert "postgres:" not in compose.lower()
    assert "stats-db:" not in compose
    assert "POSTGRES_PASSWORD" not in compose
    assert "DATABASE_URL" not in compose


def test_dockerfile_includes_azure_sql_driver_dependencies():
    dockerfile = read(DOCKERFILE)

    assert "msodbcsql18" in dockerfile
    assert "unixodbc" in dockerfile
    assert "import pyodbc" in dockerfile

# M9 End
