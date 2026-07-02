"""M12 - Email Ingestion Module Start
Provides a secret-boundary abstraction for mailbox and PDF passwords.
M12 End"""

import base64
import hashlib
import logging
import os
import re

from app.config import settings
from app.services import sql_store


logger = logging.getLogger(__name__)

_memory_secrets: dict[str, str] = {}
_key_vault_client = None
_SECRET_ENV_PREFIX = "STATS_EMAIL_SECRET_"
_SECRET_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,125}[a-z0-9])?$")

# Operator-facing message used when a saved secret exists but cannot be decrypted
# with the current runtime key. This is a configuration/key-state problem, not a
# generic server error, so callers surface it as an actionable message rather than
# a raw 500. The raw secret and key material are never included.
SECRET_UNREADABLE_MESSAGE = (
    "Saved mailbox password could not be read. Re-save the mailbox app password "
    "or check the runtime email secret key."
)


class SecretResolutionError(RuntimeError):
    """Raised when a stored secret exists but cannot be decrypted/read safely."""


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


def delete_secret(secret_ref: str | None) -> None:
    """Best-effort removal of a stored secret when its owning profile is deleted.

    Failures are logged and swallowed: an undeletable secret must not block the
    profile delete, and the orphaned entry can still be rotated/purged manually.
    """
    if not secret_ref:
        return
    try:
        secret_name = normalize_secret_ref(secret_ref)
    except ValueError:
        return
    _memory_secrets.pop(secret_name, None)
    try:
        if _use_key_vault_secret_store():
            _key_vault_secret_client().begin_delete_secret(secret_name)
        elif _use_azure_sql_secret_store():
            with sql_store.connect() as connection:
                cursor = connection.cursor()
                cursor.execute(
                    f"DELETE FROM {sql_store.qualified('email_ingestion_secrets')} WHERE secret_ref = ?",
                    secret_name,
                )
                connection.commit()
    except Exception as exc:  # pragma: no cover - best-effort cleanup guard
        logger.warning("M12 secret delete failed. secret_ref=%s error=%s", secret_name, str(exc))


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


def _fernet():
    from cryptography.fernet import Fernet

    key_material = settings.email_secret_encryption_key
    if not key_material:
        raise RuntimeError("EMAIL_SECRET_ENCRYPTION_KEY or ACCESS_TOKEN_SECRET_KEY is required for SQL-backed email secrets.")
    # The Fernet key is an unsalted SHA-256 of the configured key material, so
    # rotating EMAIL_SECRET_ENCRYPTION_KEY invalidates every stored ciphertext at
    # once; resolve_secret then surfaces SECRET_UNREADABLE_MESSAGE and operators
    # re-save the mailbox passwords.
    key = base64.urlsafe_b64encode(hashlib.sha256(key_material.encode("utf-8")).digest())
    return Fernet(key)


def _store_secret_sql(secret_ref: str, value: str) -> None:
    encrypted_value = _fernet().encrypt(value.encode("utf-8"))
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"""
            MERGE {sql_store.qualified('email_ingestion_secrets')} AS target
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
    with sql_store.connect() as connection:
        cursor = connection.cursor()
        cursor.execute(
            f"SELECT encrypted_value FROM {sql_store.qualified('email_ingestion_secrets')} WHERE secret_ref = ?",
            secret_ref,
        )
        row = cursor.fetchone()
    if not row:
        return None
    encrypted_value = bytes(row.encrypted_value)
    try:
        return _fernet().decrypt(encrypted_value).decode("utf-8")
    except Exception as exc:
        # InvalidToken (wrong/rotated key), corrupt ciphertext, or bad key material
        # all land here. Surface a controlled, actionable error instead of a 500,
        # without leaking the ciphertext or key.
        raise SecretResolutionError(SECRET_UNREADABLE_MESSAGE) from exc
