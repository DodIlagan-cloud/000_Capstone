"""Apply the idempotent M12 run-history migration from inside stats-runtime.

This helper is evidence-safe: it prints database identity and column presence,
but never prints connection strings or secrets.
"""

from __future__ import annotations

import os
import pyodbc


def _connection_string() -> str:
    connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING") or os.environ.get("SQL_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit("AZURE_SQL_CONNECTIONSTRING is not configured in the runtime container")
    if "Driver=" not in connection_string:
        connection_string = "Driver={ODBC Driver 18 for SQL Server};" + connection_string
    return (
        connection_string
        .replace("Initial Catalog=", "Database=")
        .replace("User ID=", "UID=")
        .replace("Password=", "PWD=")
        .replace("Encrypt=True", "Encrypt=yes")
        .replace("Encrypt=False", "Encrypt=no")
        .replace("TrustServerCertificate=True", "TrustServerCertificate=yes")
        .replace("TrustServerCertificate=False", "TrustServerCertificate=no")
    )


def main() -> None:
    with pyodbc.connect(_connection_string(), timeout=20, autocommit=True) as connection:
        _apply_migration(connection)
        row = connection.execute(
            """
            SELECT
                DB_NAME() AS database_name,
                @@SERVERNAME AS server_name,
                COL_LENGTH('dbo.email_ingestion_runs', 'password_failed_count') AS password_failed_count_col,
                COL_LENGTH('dbo.email_ingestion_run_candidates', 'original_sha256') AS original_sha256_col;
            """
        ).fetchone()
        print("M12 run-history migration check")
        print(f"database={row.database_name} server={row.server_name}")
        print(f"password_failed_count_col={row.password_failed_count_col}")
        print(f"original_sha256_col={row.original_sha256_col}")
        if row.password_failed_count_col is None or row.original_sha256_col is None:
            raise SystemExit("Result: FAILED")
    print("Result: PASSED")


def _exists(connection, sql: str) -> bool:
    return connection.execute(sql).fetchone()[0] is not None


def _apply_migration(connection) -> None:
    if not _exists(connection, "SELECT OBJECT_ID('dbo.email_ingestion_runs', 'U')"):
        connection.execute(
            """
            CREATE TABLE dbo.email_ingestion_runs (
                run_id nvarchar(80) NOT NULL CONSTRAINT pk_email_ingestion_runs PRIMARY KEY,
                source_id nvarchar(120) NOT NULL,
                mode nvarchar(40) NOT NULL CONSTRAINT df_email_runs_mode DEFAULT 'dry_run',
                status nvarchar(40) NOT NULL,
                started_at_utc datetime2(3) NULL,
                completed_at_utc datetime2(3) NULL,
                correlation_id nvarchar(80) NULL,
                error_message nvarchar(2000) NULL,
                summary_json nvarchar(max) NOT NULL CONSTRAINT df_email_runs_summary DEFAULT '{}',
                message_count int NOT NULL CONSTRAINT df_email_runs_message_count DEFAULT 0,
                attachment_count int NOT NULL CONSTRAINT df_email_runs_attachment_count DEFAULT 0,
                retrieved_count int NOT NULL CONSTRAINT df_email_runs_retrieved_count DEFAULT 0,
                handed_off_count int NOT NULL CONSTRAINT df_email_runs_handed_off_count DEFAULT 0,
                skipped_count int NOT NULL CONSTRAINT df_email_runs_skipped_count DEFAULT 0,
                duplicate_count int NOT NULL CONSTRAINT df_email_runs_duplicate_count DEFAULT 0,
                failed_count int NOT NULL CONSTRAINT df_email_runs_failed_count DEFAULT 0,
                password_required_count int NOT NULL CONSTRAINT df_email_runs_password_required_count DEFAULT 0,
                password_failed_count int NOT NULL CONSTRAINT df_email_runs_password_failed_count DEFAULT 0,
                created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_runs_created_at DEFAULT SYSUTCDATETIME()
            );
            """
        )
    if not _exists(connection, "SELECT COL_LENGTH('dbo.email_ingestion_runs', 'password_failed_count')"):
        connection.execute(
            """
            ALTER TABLE dbo.email_ingestion_runs
                ADD password_failed_count int NOT NULL
                    CONSTRAINT df_email_runs_password_failed_count DEFAULT 0;
            """
        )
    if not _exists(
        connection,
        "SELECT name FROM sys.indexes WHERE name = 'ix_email_runs_source_started' "
        "AND object_id = OBJECT_ID('dbo.email_ingestion_runs')",
    ):
        connection.execute(
            """
            CREATE INDEX ix_email_runs_source_started
                ON dbo.email_ingestion_runs(source_id, started_at_utc DESC);
            """
        )

    if not _exists(connection, "SELECT OBJECT_ID('dbo.email_ingestion_run_candidates', 'U')"):
        connection.execute(
            """
            CREATE TABLE dbo.email_ingestion_run_candidates (
                id bigint IDENTITY(1, 1) NOT NULL CONSTRAINT pk_email_ingestion_run_candidates PRIMARY KEY,
                run_id nvarchar(80) NOT NULL,
                source_id nvarchar(120) NOT NULL,
                candidate_id nvarchar(80) NOT NULL,
                filename nvarchar(400) NOT NULL,
                status nvarchar(40) NOT NULL,
                sender nvarchar(400) NULL,
                subject_redacted nvarchar(400) NULL,
                received_at nvarchar(80) NULL,
                message_id nvarchar(400) NULL,
                attachment_id nvarchar(120) NULL,
                sha256 nvarchar(80) NULL,
                original_sha256 nvarchar(80) NULL,
                dedup_key nvarchar(700) NULL,
                handoff_ingestion_id nvarchar(120) NULL,
                handoff_status nvarchar(40) NULL,
                handoff_content_reference nvarchar(1000) NULL,
                handoff_error nvarchar(2000) NULL,
                finding_codes_json nvarchar(max) NOT NULL CONSTRAINT df_email_run_candidates_findings DEFAULT '[]',
                created_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_run_candidates_created_at DEFAULT SYSUTCDATETIME(),
                CONSTRAINT fk_email_run_candidates_run FOREIGN KEY (run_id)
                    REFERENCES dbo.email_ingestion_runs(run_id) ON DELETE CASCADE
            );
            """
        )
    if not _exists(
        connection,
        "SELECT name FROM sys.indexes WHERE name = 'ix_email_run_candidates_run' "
        "AND object_id = OBJECT_ID('dbo.email_ingestion_run_candidates')",
    ):
        connection.execute(
            """
            CREATE INDEX ix_email_run_candidates_run
                ON dbo.email_ingestion_run_candidates(run_id);
            """
        )
    if not _exists(connection, "SELECT COL_LENGTH('dbo.email_ingestion_run_candidates', 'original_sha256')"):
        connection.execute(
            """
            ALTER TABLE dbo.email_ingestion_run_candidates
                ADD original_sha256 nvarchar(80) NULL;
            """
        )
    if not _exists(
        connection,
        "SELECT name FROM sys.indexes WHERE name = 'ix_email_run_candidates_dedup_status' "
        "AND object_id = OBJECT_ID('dbo.email_ingestion_run_candidates')",
    ):
        connection.execute(
            """
            CREATE INDEX ix_email_run_candidates_dedup_status
                ON dbo.email_ingestion_run_candidates(dedup_key) INCLUDE (status);
            """
        )
    if not _exists(connection, "SELECT OBJECT_ID('dbo.email_ingestion_processed', 'U')"):
        connection.execute(
            """
            CREATE TABLE dbo.email_ingestion_processed (
                ingestion_id nvarchar(120) NOT NULL CONSTRAINT pk_email_ingestion_processed PRIMARY KEY,
                document_id nvarchar(120) NULL,
                run_id nvarchar(80) NULL,
                processed_at_utc datetime2(3) NOT NULL CONSTRAINT df_email_processed_at DEFAULT SYSUTCDATETIME()
            );
            """
        )


if __name__ == "__main__":
    main()
