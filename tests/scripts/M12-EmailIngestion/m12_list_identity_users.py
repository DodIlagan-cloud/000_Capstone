"""List non-secret Stats identity users for local evidence login selection."""

from __future__ import annotations

import os

import pyodbc


def _connection_string() -> str:
    connection_string = os.environ.get("AZURE_SQL_CONNECTIONSTRING") or os.environ.get("SQL_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit("missing SQL connection string")
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
    with pyodbc.connect(_connection_string(), timeout=20) as connection:
        cursor = connection.cursor()
        for table in ("users", "app_users", "identity_users"):
            try:
                cursor.execute(f"SELECT TOP (10) * FROM dbo.{table}")
                rows = cursor.fetchall()
                columns = [item[0] for item in cursor.description]
            except Exception as exc:
                print(f"NO {table}: {str(exc)[:120]}")
                continue
            print(f"TABLE {table}: {len(rows)} row(s)")
            print("columns=" + ",".join(columns))
            for row in rows:
                visible = []
                for column, value in zip(columns, row):
                    if "hash" in column.lower() or "password" in column.lower() or "secret" in column.lower():
                        continue
                    visible.append(f"{column}={value}")
                print("; ".join(visible))


if __name__ == "__main__":
    main()
