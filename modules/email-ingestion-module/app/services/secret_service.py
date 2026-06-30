"""M12 - Email Ingestion Module Start
Provides a secret-boundary abstraction for mailbox and PDF passwords.
M12 End"""

import base64
import hashlib
import os
import re

from app.config import settings


_memory_secrets: dict[str, str] = {}
_key_vault_client = None
_SECRET_ENV_PREFIX = "STATS_EMAIL_SECRET_"
_SECRET_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,125}[a-z0-9])?$")


def normalize_secret_ref(secret_ref: str) -> str:
    raw_value = (secret_ref or "").strip()
    normalized = re.sub(r"[^a-zA-Z0-9-]+", "-", raw_value).strip("-").lower()
    normalized = normalized or "stats-email-secret"
    if normalized != raw_value.lower() or len(normalized) > 127:
        suffix = hashlib.sha256(raw_value.encode("utf-8")).hexdigest()[:12]
        normalized = f"{normalized[:114].rstrip('-')}-{suffix}"
    if not _SECRET_NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Secret reference must normalize to a valid secret name.")
    return normalized


def secret_name_for_source(source_id: str, provider: str = "imap") -> str:
    safe_source_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", source_id).strip("-").lower()
    safe_provider = re.sub(r"[^a-zA-Z0-9-]+", "-", provider.replace("_", "-")).strip("-").lower()
    return normalize_secret_ref(f"stats-email-{safe_provider}-app-password-{safe_source_id}")


def store_secret(secret_ref: str | None, value: str | None) -> None:
    """Store a secret value behind a stable reference without returning it through APIs."""
    if not secret_ref or not value:
        return
    secret_name = normalize_secret_ref(secret_ref)
    if _use_key_vault_secret_store():
        _store_secret_key_vault(secret_name, value)
        return
    if _use_azure_sql_secret_store():
        _store_secret_sql(secret_name, value)
        return
    _memory_secrets[secret_name] = value


def resolve_secret(secret_ref: str | None) -> str | None:
    """Resolve a secret reference without exposing the value in API responses."""
    if not secret_ref:
        return None
    secret_name = normalize_secret_ref(secret_ref)
    memory_value = _memory_secrets.get(secret_name)
    if memory_value:
        return memory_value
    if _use_key_vault_secret_store():
        return _resolve_secret_key_vault(secret_name)
    if _use_azure_sql_secret_store():
        sql_value = _resolve_secret_sql(secret_name)
        if sql_value:
            return sql_value
    if _use_environment_secret_store():
        return os.environ.get(_environment_secret_name(secret_name))
    return None


def clear_cached_secrets() -> None:
    _memory_secrets.clear()


def _use_azure_sql_secret_store() -> bool:
    return settings.email_secret_provider.lower() in {"azure_sql", "sql"} and bool(settings.azure_sql_connectionstring)


def _use_environment_secret_store() -> bool:
    return settings.email_secret_provider.lower() in {"environment", "env"}


def _use_key_vault_secret_store() -> bool:
    return settings.email_secret_provider.lower() in {"azure_key_vault", "key_vault"} and bool(settings.email_key_vault_url)


def _environment_secret_name(secret_name: str) -> str:
    return f"{_SECRET_ENV_PREFIX}{secret_name.upper().replace('-', '_')}"


def _key_vault_secret_client():
    global _key_vault_client
    if _key_vault_client is None:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        credential = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        _key_vault_client = SecretClient(vault_url=settings.email_key_vault_url, credential=credential)
    return _key_vault_client


def _store_secret_key_vault(secret_ref: str, value: str) -> None:
    _key_vault_secret_client().set_secret(secret_ref, value)


def _resolve_secret_key_vault(secret_ref: str) -> str | None:
    try:
        return _key_vault_secret_client().get_secret(secret_ref).value
    except Exception as exc:
        if exc.__class__.__name__ == "ResourceNotFoundError":
            return None
        raise


def _connection_string() -> str:
    connection_string = settings.azure_sql_connectionstring or ""
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


def _connect_sql():
    import pyodbc

    return pyodbc.connect(_connection_string(), timeout=10, autocommit=False)


def _fernet():
    from cryptography.fernet import Fernet

    key_material = settings.email_secret_encryption_key
    if not key_material:
        raise RuntimeError("EMAIL_SECRET_ENCRYPTION_KEY or ACCESS_TOKEN_SECRET_KEY is required for SQL-backed email secrets.")
    key = base64.urlsafe_b64encode(hashlib.sha256(key_material.encode("utf-8")).digest())
    return Fernet(key)


def _store_secret_sql(secret_ref: str, value: str) -> None:
    encrypted_value = _fernet().encrypt(value.encode("utf-8"))
    with _connect_sql() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            MERGE dbo.email_ingestion_secrets AS target
            USING (SELECT ? AS secret_ref) AS source
                ON target.secret_ref = source.secret_ref
            WHEN MATCHED THEN UPDATE SET
                encrypted_value = ?, updated_at_utc = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (secret_ref, encrypted_value)
                VALUES (?, ?);
            """,
            secret_ref,
            encrypted_value,
            secret_ref,
            encrypted_value,
        )
        connection.commit()


def _resolve_secret_sql(secret_ref: str) -> str | None:
    with _connect_sql() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT encrypted_value FROM dbo.email_ingestion_secrets WHERE secret_ref = ?",
            secret_ref,
        )
        row = cursor.fetchone()
    if not row:
        return None
    encrypted_value = bytes(row.encrypted_value)
    return _fernet().decrypt(encrypted_value).decode("utf-8")
