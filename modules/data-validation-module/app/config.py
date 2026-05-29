import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M8 - Data Validation Module Start
# Loads data validation runtime defaults from committed config before local overrides.
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
    default_currency: str
    min_record_confidence: float
    duplicate_match_amount_tolerance: float
    require_transaction_date: bool
    require_transaction_direction: bool
    enable_duplicate_detection: bool
    max_records_per_request: int

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
        self.default_currency = _config_value(config_values, "DEFAULT_CURRENCY").upper()
        self.min_record_confidence = _parse_float(_config_value(config_values, "MIN_RECORD_CONFIDENCE"), 0.65)
        self.duplicate_match_amount_tolerance = _parse_float(
            _config_value(config_values, "DUPLICATE_MATCH_AMOUNT_TOLERANCE"),
            0.01,
        )
        self.require_transaction_date = _parse_bool(
            _config_value(config_values, "REQUIRE_TRANSACTION_DATE"),
            True,
        )
        self.require_transaction_direction = _parse_bool(
            _config_value(config_values, "REQUIRE_TRANSACTION_DIRECTION"),
            True,
        )
        self.enable_duplicate_detection = _parse_bool(
            _config_value(config_values, "ENABLE_DUPLICATE_DETECTION"),
            True,
        )
        self.max_records_per_request = _parse_int(
            _config_value(config_values, "MAX_RECORDS_PER_REQUEST"),
            1000,
        )

    @staticmethod
    def _parse_csv_values(value: str | None) -> List[str]:
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


settings = Settings()
# M8 End
