"""M12 - Email Ingestion Module Start
Loads email ingestion runtime defaults from committed config before local overrides.
M12 End"""

import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_FILE = SERVICE_ROOT / "config" / "defaults.env"
LOCAL_CONFIG_FILE = SERVICE_ROOT / ".env"

# The module now verifies bearer tokens with ACCESS_TOKEN_SECRET_KEY (see
# app/services/auth_service.py), so a shipped placeholder key would let forged
# tokens pass in production. These mirror the identity module's guard.
MIN_PRODUCTION_SECRET_LENGTH = 32
PLACEHOLDER_SECRET_MARKERS = (
    "change-me",
    "changeme",
    "replace-with",
    "development-only",
    "placeholder",
    "example",
)


def _load_config_values() -> dict[str, str]:
    loaded_values = {
        key: value
        for config_file in (DEFAULT_CONFIG_FILE, LOCAL_CONFIG_FILE)
        for key, value in dotenv_values(config_file).items()
        if value is not None
    }
    return {**loaded_values, **os.environ}


def _config_value(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None:
        raise RuntimeError(f"Missing required setting: {key}")
    return value


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


class Settings:
    """Application settings loaded from config files and environment variables."""

    app_name: str
    app_version: str
    debug: bool
    api_prefix: str
    api_host: str
    api_port: int
    cors_allowed_origins: List[str]
    log_level: str
    access_token_secret_key: str
    access_token_algorithm: str
    email_provider: str
    email_ingestion_mode: str
    file_ingestion_base_url: str
    stats_internal_api_key: str | None
    email_source_config_store: str
    email_secret_provider: str
    email_secret_encryption_key: str | None
    email_key_vault_url: str | None
    allowed_attachment_extensions: list[str]
    allowed_attachment_mime_types: list[str]
    max_attachment_size_bytes: int
    default_mailbox_folder: str
    default_lookback_hours: int
    default_max_messages: int
    polling_enabled: bool
    redact_email_subjects: bool
    pdf_password_secret_prefix: str
    block_private_imap_hosts: bool
    allowed_imap_hosts: list[str]
    azure_sql_connectionstring: str | None
    database_schema: str

    def __init__(self):
        config_values = _load_config_values()

        self.app_name = _config_value(config_values, "APP_NAME")
        self.app_version = _config_value(config_values, "APP_VERSION")
        self.debug = _parse_bool(_config_value(config_values, "DEBUG"))
        self.api_prefix = _config_value(config_values, "API_PREFIX")
        self.api_host = _config_value(config_values, "API_HOST")
        self.api_port = _parse_int(_config_value(config_values, "API_PORT"), 0)
        self.cors_allowed_origins = self._parse_csv_values(_config_value(config_values, "CORS_ALLOWED_ORIGINS"))
        self.log_level = _config_value(config_values, "LOG_LEVEL")
        self.access_token_secret_key = _config_value(config_values, "ACCESS_TOKEN_SECRET_KEY")
        self.access_token_algorithm = _config_value(config_values, "ACCESS_TOKEN_ALGORITHM")
        self._validate_access_token_secret()
        self.email_provider = _config_value(config_values, "EMAIL_PROVIDER")
        self.email_ingestion_mode = _config_value(config_values, "EMAIL_INGESTION_MODE")
        self.file_ingestion_base_url = _config_value(config_values, "FILE_INGESTION_BASE_URL").rstrip("/")
        self.stats_internal_api_key = config_values.get("STATS_INTERNAL_API_KEY")
        self.email_source_config_store = _config_value(config_values, "EMAIL_SOURCE_CONFIG_STORE")
        self.email_secret_provider = _config_value(config_values, "EMAIL_SECRET_PROVIDER")
        self.email_secret_encryption_key = self._email_secret_encryption_key(config_values)
        self.email_key_vault_url = (
            config_values.get("EMAIL_KEY_VAULT_URL")
            or config_values.get("AZURE_KEY_VAULT_URI")
            or config_values.get("KEY_VAULT_URI")
        )
        self.allowed_attachment_extensions = [
            value.lower() for value in self._parse_csv_values(_config_value(config_values, "ALLOWED_ATTACHMENT_EXTENSIONS"))
        ]
        self.allowed_attachment_mime_types = [
            value.lower() for value in self._parse_csv_values(_config_value(config_values, "ALLOWED_ATTACHMENT_MIME_TYPES"))
        ]
        self.max_attachment_size_bytes = _parse_int(_config_value(config_values, "MAX_ATTACHMENT_SIZE_BYTES"), 0)
        self.default_mailbox_folder = _config_value(config_values, "DEFAULT_MAILBOX_FOLDER")
        self.default_lookback_hours = _parse_int(_config_value(config_values, "DEFAULT_LOOKBACK_HOURS"), 24)
        self.default_max_messages = _parse_int(_config_value(config_values, "DEFAULT_MAX_MESSAGES"), 25)
        self.polling_enabled = _parse_bool(_config_value(config_values, "POLLING_ENABLED"), False)
        self.redact_email_subjects = _parse_bool(_config_value(config_values, "REDACT_EMAIL_SUBJECTS"), True)
        self.pdf_password_secret_prefix = _config_value(config_values, "PDF_PASSWORD_SECRET_PREFIX")
        self.block_private_imap_hosts = _parse_bool(config_values.get("BLOCK_PRIVATE_IMAP_HOSTS"), True)
        self.allowed_imap_hosts = self._parse_csv_values(config_values.get("ALLOWED_IMAP_HOSTS"))
        self.azure_sql_connectionstring = config_values.get("AZURE_SQL_CONNECTIONSTRING")
        self.database_schema = config_values.get("DATABASE_SCHEMA", "dbo")

    @staticmethod
    def _parse_csv_values(value: str | None) -> list[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    def _validate_access_token_secret(self) -> None:
        if self.debug:
            return

        secret = self.access_token_secret_key.strip()
        lowered = secret.lower()
        looks_like_placeholder = any(marker in lowered for marker in PLACEHOLDER_SECRET_MARKERS)
        if looks_like_placeholder or len(secret) < MIN_PRODUCTION_SECRET_LENGTH:
            raise RuntimeError(
                "ACCESS_TOKEN_SECRET_KEY must be overridden with a non-placeholder value "
                f"of at least {MIN_PRODUCTION_SECRET_LENGTH} characters when DEBUG=false. "
                "The Email Ingestion API verifies bearer tokens with this key."
            )

    def _email_secret_encryption_key(self, config_values: dict[str, str]) -> str | None:
        dedicated_key = (config_values.get("EMAIL_SECRET_ENCRYPTION_KEY") or "").strip()
        if dedicated_key:
            return dedicated_key

        fallback_key = (config_values.get("ACCESS_TOKEN_SECRET_KEY") or "").strip()
        if not fallback_key:
            return None

        if not self.debug and self.email_secret_provider.lower() in {"azure_sql", "sql"}:
            raise RuntimeError(
                "EMAIL_SECRET_ENCRYPTION_KEY must be set when EMAIL_SECRET_PROVIDER=azure_sql and DEBUG=false. "
                "Do not reuse ACCESS_TOKEN_SECRET_KEY for SQL-backed email secret encryption in production."
            )

        return fallback_key


settings = Settings()
