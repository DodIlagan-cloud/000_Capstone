"""M9 - Stats Data and Persistence Start
Applies Stats Data Azure SQL migrations without printing secret values.
M9 End"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pyodbc


def _normalize_connection_string(connection_string: str) -> str:
    """Normalize Azure portal-style SQL connection strings for pyodbc."""
    if not connection_string:
        raise RuntimeError("Missing required setting: AZURE_SQL_CONNECTIONSTRING")

    if "Driver=" not in connection_string:
        connection_string = "Driver={ODBC Driver 18 for SQL Server};" + connection_string

    replacements = {
        "Initial Catalog=": "Database=",
        "User ID=": "UID=",
        "Password=": "PWD=",
        "Encrypt=True": "Encrypt=yes",
        "Encrypt=False": "Encrypt=no",
        "TrustServerCertificate=True": "TrustServerCertificate=yes",
        "TrustServerCertificate=False": "TrustServerCertificate=no",
    }
    for old, new in replacements.items():
        connection_string = connection_string.replace(old, new)

    return connection_string


def _migration_dir() -> Path:
    configured = os.environ.get("STATS_DATA_MIGRATIONS_DIR")
    if configured:
        return Path(configured)

    app_root = Path(os.environ.get("STATS_APP_ROOT", Path.cwd()))
    return app_root / "apps" / "stats-data" / "migrations" / "azure-sql"


def _split_batches(sql_text: str) -> list[str]:
    """Split a T-SQL script on standalone GO batch separators."""
    batches = re.split(r"(?im)^\s*GO\s*;?\s*$", sql_text)
    return [batch.strip() for batch in batches if batch.strip()]


def _apply_migration(cursor: pyodbc.Cursor, migration_file: Path) -> None:
    sql_text = migration_file.read_text(encoding="utf-8")
    for batch in _split_batches(sql_text):
        cursor.execute(batch)


def main() -> int:
    provider = os.environ.get("DATABASE_PROVIDER", "AzureSql")
    if provider.lower() != "azuresql":
        print("[M9] ERROR: DATABASE_PROVIDER must be AzureSql for Stats Data migrations.", file=sys.stderr)
        return 1

    migrations_dir = _migration_dir()
    if not migrations_dir.exists():
        print(f"[M9] ERROR: Azure SQL migrations directory not found: {migrations_dir}", file=sys.stderr)
        return 1

    migration_files = sorted(migrations_dir.glob("*.sql"))
    if not migration_files:
        print(f"[M9] ERROR: No Azure SQL migration files found in: {migrations_dir}", file=sys.stderr)
        return 1

    connection_string = _normalize_connection_string(os.environ.get("AZURE_SQL_CONNECTIONSTRING", ""))
    connection = pyodbc.connect(connection_string, timeout=30, autocommit=False)

    try:
        cursor = connection.cursor()
        for migration_file in migration_files:
            print(f"[M9] Applying Azure SQL migration: {migration_file.name}")
            _apply_migration(cursor, migration_file)
            connection.commit()
        print(f"[M9] Azure SQL migration bootstrap complete. Applied/verified {len(migration_files)} migration file(s).")
    except Exception:
        connection.rollback()
        print("[M9] ERROR: Azure SQL migration bootstrap failed.", file=sys.stderr)
        raise
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
