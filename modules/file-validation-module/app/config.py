import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M3 - File Validation Module Start
# Loads file validation runtime defaults from committed config before local overrides.
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
# M3 End


def _parse_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class Settings:
    """Application settings loaded from config files and environment variables."""

    # M3 - File Validation Module Start
    # Declares runtime settings used by the standalone validation API and policy defaults.
    app_name: str
    app_version: str
    debug: bool
    api_prefix: str
    api_host: str
    api_port: int
    cors_allowed_origins: List[str]
    log_level: str
    max_file_size_bytes: int
    allowed_extensions: List[str]
    allowed_mime_types: List[str]
    require_known_signature: bool
    compute_sha256: bool
    # M3 End

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
        self.max_file_size_bytes = _parse_int(
            _config_value(config_values, "MAX_FILE_SIZE_BYTES"),
            0,
        )
        self.allowed_extensions = self._parse_csv_values(
            _config_value(config_values, "ALLOWED_EXTENSIONS"),
            normalize_extension=True,
        )
        self.allowed_mime_types = self._parse_csv_values(
            _config_value(config_values, "ALLOWED_MIME_TYPES"),
            lowercase=True,
        )
        self.require_known_signature = _parse_bool(
            _config_value(config_values, "REQUIRE_KNOWN_SIGNATURE")
        )
        self.compute_sha256 = _parse_bool(_config_value(config_values, "COMPUTE_SHA256"))

    @staticmethod
    def _parse_csv_values(
        value: str | None,
        normalize_extension: bool = False,
        lowercase: bool = False,
    ) -> List[str]:
        if not value:
            return []

        values = []
        for configured_value in value.split(","):
            normalized_value = configured_value.strip()
            if normalize_extension and normalized_value and not normalized_value.startswith("."):
                normalized_value = f".{normalized_value}"
            if lowercase:
                normalized_value = normalized_value.lower()
            if normalized_value:
                values.append(normalized_value.lower() if normalize_extension else normalized_value)

        return values


settings = Settings()
