"""Reset the dedicated M12 evidence admin password.

Reads STATS_EVIDENCE_ADMIN_PASSWORD from the environment and updates only
m12.evidence.admin@example.test. The password value is never printed.
"""

from __future__ import annotations

import base64
import hashlib
import os

import pyodbc


EMAIL = "m12.evidence.admin@example.test"
PASSWORD_ITERATIONS = 260_000


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


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
    password = os.environ.get("STATS_EVIDENCE_ADMIN_PASSWORD", "")
    if not password:
        raise SystemExit("STATS_EVIDENCE_ADMIN_PASSWORD is required")
    with pyodbc.connect(_connection_string(), timeout=20, autocommit=True) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE dbo.users
            SET hashed_password = ?, must_change_password = 0, updated_at = SYSUTCDATETIME()
            WHERE email = ? AND role = 'admin';
            """,
            _hash_password(password),
            EMAIL,
        )
        print("M12 evidence admin password reset")
        print(f"email={EMAIL}")
        print(f"rows_updated={cursor.rowcount}")
        if cursor.rowcount != 1:
            raise SystemExit("Result: FAILED")
    print("Result: PASSED")


if __name__ == "__main__":
    main()
