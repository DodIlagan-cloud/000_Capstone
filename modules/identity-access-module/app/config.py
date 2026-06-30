import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M1 - User Access Management Start
# Loads backend runtime defaults from committed config before local overrides and environment variables.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_FILE = SERVICE_ROOT / "config" / "defaults.env"
LOCAL_CONFIG_FILE = SERVICE_ROOT / ".env"
PLACEHOLDER_ACCESS_TOKEN_SECRET = "development-only-change-me"
# Substrings that indicate an unreplaced example/placeholder secret. Rejected
# in production even when long enough to pass the length check.
PLACEHOLDER_SECRET_MARKERS = (
    "change-me",
    "changeme",
    "replace-with",
    "development-only",
    "placeholder",
    "example",
)
MIN_PRODUCTION_SECRET_LENGTH = 32


def _load_config_values() -> dict[str, str]:
    """Load committed defaults, local config overrides, and environment overrides."""
    loaded_values = {
        key: value
        for config_file in (DEFAULT_CONFIG_FILE, LOCAL_CONFIG_FILE)
        for key, value in dotenv_values(config_file).items()
        if value is not None
    }
    return {**loaded_values, **os.environ}


def _config_value(values: dict[str, str], key: str) -> str:
    """Return a configured runtime value or fail with the missing key name."""
    value = values.get(key)
    if value is None:
        raise RuntimeError(f"Missing required setting: {key}")

    return value
# M1 End


def _parse_bool(value: str, default: bool = False) -> bool:
    """Parse common environment-style boolean values."""
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str, default: int) -> int:
    """Parse an integer setting with a safe fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Settings:
    """Application settings loaded from config files and environment variables."""

    # M1 - User Access Management Start
    # Declares runtime settings that are populated from config files during startup.
    app_name: str
    app_version: str
    debug: bool
    api_prefix: str
    api_host: str
    api_port: int
    cors_allowed_origins: List[str]

    # Declares the primary application database target for configured startup.
    database_provider: str
    database_url: str
    azure_sql_connectionstring: str
    database_echo: bool
    log_level: str

    # Defines authentication settings for token, password, and first-admin handling.
    access_token_secret_key: str
    access_token_algorithm: str
    access_token_expire_minutes: int
    password_hash_scheme: str
    default_admin_email: str
    default_admin_password: str
    # M1 End

    def __init__(self):
        config_values = _load_config_values()

        self.app_name = _config_value(config_values, "APP_NAME")
        self.app_version = _config_value(config_values, "APP_VERSION")
        self.debug = _parse_bool(_config_value(config_values, "DEBUG"))
        self.api_prefix = _config_value(config_values, "API_PREFIX")
        self.api_host = _config_value(config_values, "API_HOST")
        self.api_port = _parse_int(_config_value(config_values, "API_PORT"), 0)
        self.cors_allowed_origins = self._parse_csv_values(
            _config_value(config_values, "CORS_ALLOWED_ORIGINS")
        )
        self.log_level = _config_value(config_values, "LOG_LEVEL")
        # M1 - User Access Management Start
        # Uses provider-aware database values while keeping environment overrides configurable.
        self.database_provider = config_values.get("DATABASE_PROVIDER", "AzureSql")
        self.database_url = config_values.get("DATABASE_URL", "")
        self.azure_sql_connectionstring = config_values.get("AZURE_SQL_CONNECTIONSTRING", "")
        if self.database_provider.lower() == "azuresql" and not self.azure_sql_connectionstring:
            raise RuntimeError("Missing required setting: AZURE_SQL_CONNECTIONSTRING")
        if self.database_provider.lower() != "azuresql" and not self.database_url:
            raise RuntimeError("Missing required setting: DATABASE_URL")
        # M1 End
        self.database_echo = _parse_bool(_config_value(config_values, "DATABASE_ECHO"))

        # M1 - User Access Management Start
        # Loads authentication settings from config files and environment variables.
        # self.access_token_secret_key = os.getenv(
        #     "ACCESS_TOKEN_SECRET_KEY",
        #     self.access_token_secret_key,
        # )
        self.access_token_secret_key = _config_value(config_values, "ACCESS_TOKEN_SECRET_KEY")
        self._validate_access_token_secret()
        # self.access_token_algorithm = os.getenv(
        #     "ACCESS_TOKEN_ALGORITHM",
        #     self.access_token_algorithm,
        # )
        self.access_token_algorithm = _config_value(config_values, "ACCESS_TOKEN_ALGORITHM")
        # self.access_token_expire_minutes = _parse_int(
        #     os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"),
        #     self.access_token_expire_minutes,
        # )
        self.access_token_expire_minutes = _parse_int(
            _config_value(config_values, "ACCESS_TOKEN_EXPIRE_MINUTES"),
            0,
        )
        # self.password_hash_scheme = os.getenv("PASSWORD_HASH_SCHEME", self.password_hash_scheme)
        self.password_hash_scheme = _config_value(config_values, "PASSWORD_HASH_SCHEME")
        # self.default_admin_email = os.getenv("DEFAULT_ADMIN_EMAIL", self.default_admin_email)
        self.default_admin_email = _config_value(config_values, "DEFAULT_ADMIN_EMAIL")
        # self.default_admin_password = os.getenv(
        #     "DEFAULT_ADMIN_PASSWORD",
        #     self.default_admin_password,
        # )
        self.default_admin_password = _config_value(config_values, "DEFAULT_ADMIN_PASSWORD")
        # M1 End

    @staticmethod
    def _parse_csv_values(value: str | None, strip_dot: bool = False) -> List[str]:
        if not value:
            return []

        values = []
        for configured_value in value.split(","):
            normalized_value = configured_value.strip()
            if normalized_value:
                values.append(normalized_value.lower().lstrip(".") if strip_dot else normalized_value)

        return values

    def _validate_access_token_secret(self) -> None:
        if self.debug:
            return

        secret = self.access_token_secret_key.strip()
        lowered = secret.lower()
        looks_like_placeholder = (
            secret == PLACEHOLDER_ACCESS_TOKEN_SECRET
            or any(marker in lowered for marker in PLACEHOLDER_SECRET_MARKERS)
        )
        if looks_like_placeholder or len(secret) < MIN_PRODUCTION_SECRET_LENGTH:
            raise RuntimeError(
                "ACCESS_TOKEN_SECRET_KEY must be overridden with a non-placeholder value "
                f"of at least {MIN_PRODUCTION_SECRET_LENGTH} characters when DEBUG=false."
            )


settings = Settings()
