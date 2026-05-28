import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M5 - Document Parsing Module Start
# Loads document parsing runtime defaults from committed config before local overrides.
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
    supported_mime_types: List[str]
    max_document_size_bytes: int
    allow_direct_text: bool
    allow_ocr_fallback: bool
    ocr_engine: str
    tesseract_cmd: str
    tessdata_prefix: str
    ocr_languages: List[str]
    supported_document_types: List[str]
    classification_confidence_threshold: float
    classification_allow_unknown: bool
    extraction_timeout_seconds: int
    max_page_count: int
    min_text_length: int
    allow_document_references: bool
    document_reference_roots: List[Path]
    redact_evidence_output: bool
    redaction_preview_chars: int

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
        self.supported_mime_types = self._parse_csv_values(
            _config_value(config_values, "SUPPORTED_MIME_TYPES"),
            lowercase=True,
        )
        self.max_document_size_bytes = _parse_int(
            _config_value(config_values, "MAX_DOCUMENT_SIZE_BYTES"),
            0,
        )
        self.allow_direct_text = _parse_bool(_config_value(config_values, "ALLOW_DIRECT_TEXT"))
        self.allow_ocr_fallback = _parse_bool(_config_value(config_values, "ALLOW_OCR_FALLBACK"))
        self.ocr_engine = _config_value(config_values, "OCR_ENGINE").lower()
        self.tesseract_cmd = _config_value(config_values, "TESSERACT_CMD")
        self.tessdata_prefix = config_values.get("TESSDATA_PREFIX", "")
        self.ocr_languages = self._parse_csv_values(_config_value(config_values, "OCR_LANGUAGES"))
        self.supported_document_types = self._parse_csv_values(
            _config_value(config_values, "SUPPORTED_DOCUMENT_TYPES"),
            lowercase=True,
        )
        self.classification_confidence_threshold = _parse_float(
            _config_value(config_values, "CLASSIFICATION_CONFIDENCE_THRESHOLD"),
            0.70,
        )
        self.classification_allow_unknown = _parse_bool(
            _config_value(config_values, "CLASSIFICATION_ALLOW_UNKNOWN"),
            True,
        )
        self.extraction_timeout_seconds = _parse_int(
            _config_value(config_values, "EXTRACTION_TIMEOUT_SECONDS"),
            30,
        )
        self.max_page_count = _parse_int(_config_value(config_values, "MAX_PAGE_COUNT"), 25)
        self.min_text_length = _parse_int(_config_value(config_values, "MIN_TEXT_LENGTH"), 20)
        self.allow_document_references = _parse_bool(
            _config_value(config_values, "ALLOW_DOCUMENT_REFERENCES"),
            True,
        )
        self.document_reference_roots = self._parse_paths(
            _config_value(config_values, "DOCUMENT_REFERENCE_ROOTS")
        )
        self.redact_evidence_output = _parse_bool(
            _config_value(config_values, "REDACT_EVIDENCE_OUTPUT"),
            True,
        )
        self.redaction_preview_chars = _parse_int(
            _config_value(config_values, "REDACTION_PREVIEW_CHARS"),
            500,
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

    @staticmethod
    def _resolve_path(value: str) -> Path:
        configured_path = Path(value)
        if configured_path.is_absolute():
            return configured_path

        return (SERVICE_ROOT / configured_path).resolve()

    def _parse_paths(self, value: str | None) -> List[Path]:
        if not value:
            return []

        return [self._resolve_path(path_value.strip()) for path_value in value.split(";") if path_value.strip()]


settings = Settings()
# M5/M6 End
