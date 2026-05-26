import os
from pathlib import Path
from typing import List


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
    """Application settings loaded from environment variables."""

    # App Configuration
    app_name: str = "Stats Ingestion Service"
    app_version: str = "1.0.0"
    debug: bool = False

    # API Configuration
    api_prefix: str = "/api/v1"

    # File Upload Configuration
    max_file_size_mb: int = 50
    allowed_extensions: List[str] = ["pdf"]
    upload_directory: str = "uploads"

    # PDF Processing Configuration
    enable_ocr: bool = True
    ocr_timeout_seconds: int = 300

    # Database Configuration
    database_url: str = "sqlite:///./stats_ingestion.db"
    database_echo: bool = False

    # Logging Configuration
    log_level: str = "INFO"

    def __init__(self):
        self.app_name = os.getenv("APP_NAME", self.app_name)
        self.app_version = os.getenv("APP_VERSION", self.app_version)
        self.debug = _parse_bool(os.getenv("DEBUG"), self.debug)
        self.api_prefix = os.getenv("API_PREFIX", "/api/v1")
        self.max_file_size_mb = _parse_int(os.getenv("MAX_FILE_SIZE_MB"), 50)
        self.allowed_extensions = self._parse_extensions(os.getenv("ALLOWED_EXTENSIONS"))
        self.enable_ocr = _parse_bool(os.getenv("ENABLE_OCR"), self.enable_ocr)
        self.ocr_timeout_seconds = _parse_int(os.getenv("OCR_TIMEOUT_SECONDS"), 300)
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.database_url = os.getenv("DATABASE_URL", "sqlite:///./stats_ingestion.db")
        self.database_echo = _parse_bool(os.getenv("DATABASE_ECHO"), self.database_echo)
        self.upload_directory = os.getenv("UPLOAD_DIRECTORY", "uploads")

        Path(self.upload_directory).mkdir(exist_ok=True)

    @staticmethod
    def _parse_extensions(value: str | None) -> List[str]:
        if not value:
            return ["pdf"]

        return [extension.strip().lower().lstrip(".") for extension in value.split(",") if extension.strip()]


settings = Settings()
