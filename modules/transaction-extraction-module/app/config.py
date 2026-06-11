import os
from pathlib import Path
from typing import List

from dotenv.main import dotenv_values


# M7 - Transaction Extraction Module Start
# Loads transaction extraction runtime defaults from committed config before local overrides.
SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
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
    enable_line_items: bool
    enable_transaction_classification: bool
    transaction_classification_vocabulary_path: Path
    transaction_classification_rules_path: Path
    spending_category_vocabulary_path: Path
    spending_category_rules_path: Path
    recognition_settings_url: str
    recognition_settings_internal_key: str
    recognition_settings_cache_seconds: int
    transaction_classification_threshold: float
    spending_category_threshold: float
    transaction_classification_ai_enabled: bool
    transaction_classification_ai_provider: str
    transaction_classification_ai_endpoint: str
    transaction_classification_ai_api_key_env: str
    transaction_classification_ai_model: str
    transaction_classification_ai_model_version: str
    transaction_classification_ai_min_confidence: float
    transaction_classification_ai_trigger_threshold: float
    transaction_classification_ai_max_chars: int

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
        self.enable_line_items = _parse_bool(
            config_values.get("ENABLE_LINE_ITEMS"),
            True,
        )
        self.enable_transaction_classification = _parse_bool(
            config_values.get("ENABLE_TRANSACTION_CLASSIFICATION"),
            True,
        )
        self.transaction_classification_vocabulary_path = self._resolve_path(
            config_values.get("TRANSACTION_CLASSIFICATION_VOCABULARY_PATH"),
            REPO_ROOT / "config" / "transaction-classification.vocabulary.json",
        )
        self.transaction_classification_rules_path = self._resolve_path(
            config_values.get("TRANSACTION_CLASSIFICATION_RULES_PATH"),
            REPO_ROOT / "config" / "transaction-classification.rules.json",
        )
        self.spending_category_vocabulary_path = self._resolve_path(
            config_values.get("SPENDING_CATEGORY_VOCABULARY_PATH"),
            REPO_ROOT / "config" / "spending-category.vocabulary.json",
        )
        self.spending_category_rules_path = self._resolve_path(
            config_values.get("SPENDING_CATEGORY_RULES_PATH"),
            REPO_ROOT / "config" / "spending-category.rules.json",
        )
        self.recognition_settings_url = (
            config_values.get("RECOGNITION_SETTINGS_URL")
            or "http://localhost:8018/api/v1/admin/recognition-settings/active"
        ).strip()
        self.recognition_settings_internal_key = (
            config_values.get("STATS_INTERNAL_API_KEY") or ""
        ).strip()
        self.recognition_settings_cache_seconds = _parse_int(
            config_values.get("RECOGNITION_SETTINGS_CACHE_SECONDS"),
            15,
        )
        self.transaction_classification_threshold = _parse_float(
            config_values.get("TRANSACTION_CLASSIFICATION_THRESHOLD"),
            0.55,
        )
        self.spending_category_threshold = _parse_float(
            config_values.get("SPENDING_CATEGORY_THRESHOLD"),
            0.55,
        )
        self.transaction_classification_ai_enabled = _parse_bool(
            config_values.get("TRANSACTION_CLASSIFICATION_AI_ENABLED"),
            False,
        )
        self.transaction_classification_ai_provider = (
            config_values.get("TRANSACTION_CLASSIFICATION_AI_PROVIDER") or "none"
        ).strip().lower()
        self.transaction_classification_ai_endpoint = (
            config_values.get("TRANSACTION_CLASSIFICATION_AI_ENDPOINT") or ""
        ).strip()
        self.transaction_classification_ai_api_key_env = (
            config_values.get("TRANSACTION_CLASSIFICATION_AI_API_KEY_ENV") or "GEMINI_API_KEY"
        ).strip()
        self.transaction_classification_ai_model = (
            config_values.get("TRANSACTION_CLASSIFICATION_AI_MODEL") or ""
        ).strip()
        self.transaction_classification_ai_model_version = (
            config_values.get("TRANSACTION_CLASSIFICATION_AI_MODEL_VERSION") or self.transaction_classification_ai_model
        ).strip()
        self.transaction_classification_ai_min_confidence = _parse_float(
            config_values.get("TRANSACTION_CLASSIFICATION_AI_MIN_CONFIDENCE"),
            0.76,
        )
        self.transaction_classification_ai_trigger_threshold = _parse_float(
            config_values.get("TRANSACTION_CLASSIFICATION_AI_TRIGGER_THRESHOLD"),
            0.70,
        )
        self.transaction_classification_ai_max_chars = _parse_int(
            config_values.get("TRANSACTION_CLASSIFICATION_AI_MAX_CHARS"),
            3000,
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
    def _resolve_path(value: str | None, default: Path) -> Path:
        if not value:
            return default
        path = Path(value)
        return path if path.is_absolute() else REPO_ROOT / path


settings = Settings()
# M7 End
