import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M7 - Transaction Extraction Module Start
# Loads transaction extraction runtime defaults from committed config before local overrides.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_FILE = SERVICE_ROOT / "config" / "defaults.env"
LOCAL_CONFIG_FILE = SERVICE_ROOT / ".env"


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


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
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
    supported_document_types: List[str]
    default_currency: str
    min_transaction_confidence: float
    max_text_chars: int
    max_page_count: int
    enable_field_extraction: bool
    enable_transaction_rows: bool

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
        self.supported_document_types = self._parse_csv_values(
            _config_value(config_values, "SUPPORTED_DOCUMENT_TYPES"),
            lowercase=True,
        )
        self.default_currency = _config_value(config_values, "DEFAULT_CURRENCY").upper()
        self.min_transaction_confidence = _parse_float(
            _config_value(config_values, "MIN_TRANSACTION_CONFIDENCE"),
            0.55,
        )
        self.max_text_chars = _parse_int(_config_value(config_values, "MAX_TEXT_CHARS"), 100000)
        self.max_page_count = _parse_int(_config_value(config_values, "MAX_PAGE_COUNT"), 25)
        self.enable_field_extraction = _parse_bool(
            _config_value(config_values, "ENABLE_FIELD_EXTRACTION"),
            True,
        )
        self.enable_transaction_rows = _parse_bool(
            _config_value(config_values, "ENABLE_TRANSACTION_ROWS"),
            True,
        )

    @staticmethod
    def _parse_csv_values(value: str | None, lowercase: bool = False) -> List[str]:
        if not value:
            return []

        values = []
        for configured_value in value.split(","):
            normalized_value = configured_value.strip()
            if lowercase:
                normalized_value = normalized_value.lower()
            if normalized_value:
                values.append(normalized_value)

        return values


settings = Settings()
# M7 End
