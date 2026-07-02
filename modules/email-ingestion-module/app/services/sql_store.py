"""M12 - Email Ingestion Module Start
Shared Azure SQL helpers for the module's stores.

Single home for the ODBC connection-string translation and schema-qualified table
names previously duplicated across secret_service, source_profile_service, and
run_history_service.
M12 End"""


from app.config import settings


def connection_string() -> str:
    value = settings.azure_sql_connectionstring or ""
    if "Driver=" not in value:
        value = "Driver={ODBC Driver 18 for SQL Server};" + value
    return (
        value
        .replace("Initial Catalog=", "Database=")
        .replace("User ID=", "UID=")
        .replace("Password=", "PWD=")
        .replace("Encrypt=True", "Encrypt=yes")
        .replace("Encrypt=False", "Encrypt=no")
        .replace("TrustServerCertificate=True", "TrustServerCertificate=yes")
        .replace("TrustServerCertificate=False", "TrustServerCertificate=no")
    )


def connect():
    import pyodbc

    return pyodbc.connect(connection_string(), timeout=10, autocommit=False)


def qualified(table_name: str) -> str:
    """Schema-qualify a table name using the configured DATABASE_SCHEMA.

    settings.database_schema is validated at startup against a strict identifier
    pattern, so interpolating it into SQL text is safe.

    NOTE: the Azure SQL migrations create the email_ingestion_* tables in dbo
    only; a non-default DATABASE_SCHEMA requires creating the tables in that
    schema as well (see migrations/azure-sql/email_ingestion_runs.sql).
    """
    return f"{settings.database_schema}.{table_name}"
