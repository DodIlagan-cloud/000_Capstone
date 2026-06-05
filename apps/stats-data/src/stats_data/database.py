"""M9 - Stats Data and Persistence Start
Creates Azure SQL connections for the Stats Data API.
M9 End"""

from __future__ import annotations

import os


def azure_sql_connection_string() -> str:
    connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING", "").strip()
    if not connection_string:
        raise RuntimeError("AZURE_SQL_CONNECTIONSTRING is required for Stats Data persistence.")

    if "Driver=" not in connection_string:
        connection_string = f"Driver={{ODBC Driver 18 for SQL Server}};{connection_string}"

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


def open_azure_sql_connection():
    provider = os.environ.get("DATABASE_PROVIDER", "AzureSql")
    if provider.lower() != "azuresql":
        raise RuntimeError("DATABASE_PROVIDER must be AzureSql for Stats Data persistence.")

    import pyodbc

    return pyodbc.connect(azure_sql_connection_string(), timeout=15)
