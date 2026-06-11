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
    ocr_psm_values: List[int]
    ocr_retry_orientations: bool
    ocr_pdf_fast_psm_values: List[int]
    ocr_image_fast_psm_values: List[int]
    ocr_fast_min_quality_score: float
    ocr_fast_min_text_length: int
    ocr_image_fast_min_quality_score: float
    ocr_image_fast_min_text_length: int
    ocr_image_fast_min_confidence: float
    ocr_pdf_render_scale: float
    ocr_min_confidence: float
    ocr_min_quality_score: float
    ocr_min_alnum_ratio: float
    supported_document_types: List[str]
    document_classification_vocabulary_path: Path
    document_classification_rules_path: Path
    recognition_settings_url: str
    recognition_settings_internal_key: str
    recognition_settings_cache_seconds: int
    classification_confidence_threshold: float
    classification_allow_unknown: bool
    classification_ai_enabled: bool
    classification_ai_provider: str
    classification_ai_endpoint: str
    classification_ai_api_key_env: str
    classification_ai_model: str
    classification_ai_model_version: str
    classification_ai_min_confidence: float
    classification_ai_trigger_threshold: float
    classification_ai_max_chars: int
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
        self.ocr_psm_values = self._parse_csv_int_values(config_values.get("OCR_PSM_VALUES", "6,11,4"))
        self.ocr_retry_orientations = _parse_bool(config_values.get("OCR_RETRY_ORIENTATIONS"), True)
        self.ocr_pdf_fast_psm_values = self._parse_csv_int_values(config_values.get("OCR_PDF_FAST_PSM_VALUES", "6,4"))
        self.ocr_image_fast_psm_values = self._parse_csv_int_values(config_values.get("OCR_IMAGE_FAST_PSM_VALUES", "6,11"))
        self.ocr_fast_min_quality_score = _parse_float(config_values.get("OCR_FAST_MIN_QUALITY_SCORE"), 0.55)
        self.ocr_fast_min_text_length = _parse_int(config_values.get("OCR_FAST_MIN_TEXT_LENGTH"), 120)
        self.ocr_image_fast_min_quality_score = _parse_float(config_values.get("OCR_IMAGE_FAST_MIN_QUALITY_SCORE"), 0.62)
        self.ocr_image_fast_min_text_length = _parse_int(config_values.get("OCR_IMAGE_FAST_MIN_TEXT_LENGTH"), 80)
        self.ocr_image_fast_min_confidence = _parse_float(config_values.get("OCR_IMAGE_FAST_MIN_CONFIDENCE"), 50.0)
        self.ocr_pdf_render_scale = _parse_float(config_values.get("OCR_PDF_RENDER_SCALE"), 2.0)
        self.ocr_min_confidence = _parse_float(config_values.get("OCR_MIN_CONFIDENCE"), 35.0)
        self.ocr_min_quality_score = _parse_float(config_values.get("OCR_MIN_QUALITY_SCORE"), 0.35)
        self.ocr_min_alnum_ratio = _parse_float(config_values.get("OCR_MIN_ALNUM_RATIO"), 0.35)
        self.supported_document_types = self._parse_csv_values(
            _config_value(config_values, "SUPPORTED_DOCUMENT_TYPES"),
            lowercase=True,
        )
        self.document_classification_vocabulary_path = self._resolve_stats_path(
            config_values.get("DOCUMENT_CLASSIFICATION_VOCABULARY_PATH", "config/document-classification.vocabulary.json")
        )
        self.document_classification_rules_path = self._resolve_stats_path(
            config_values.get("DOCUMENT_CLASSIFICATION_RULES_PATH", "config/document-classification.rules.json")
        )
        self.recognition_settings_url = config_values.get(
            "RECOGNITION_SETTINGS_URL",
            "http://localhost:8018/api/v1/admin/recognition-settings/active",
        ).strip()
        self.recognition_settings_internal_key = config_values.get("STATS_INTERNAL_API_KEY", "").strip()
        self.recognition_settings_cache_seconds = _parse_int(
            config_values.get("RECOGNITION_SETTINGS_CACHE_SECONDS"),
            15,
        )
        self.classification_confidence_threshold = _parse_float(
            _config_value(config_values, "CLASSIFICATION_CONFIDENCE_THRESHOLD"),
            0.70,
        )
        self.classification_allow_unknown = _parse_bool(
            _config_value(config_values, "CLASSIFICATION_ALLOW_UNKNOWN"),
            True,
        )
        self.classification_ai_enabled = _parse_bool(config_values.get("CLASSIFICATION_AI_ENABLED"), False)
        self.classification_ai_provider = config_values.get("CLASSIFICATION_AI_PROVIDER", "none").strip().lower()
        self.classification_ai_endpoint = config_values.get("CLASSIFICATION_AI_ENDPOINT", "").strip()
        self.classification_ai_api_key_env = config_values.get("CLASSIFICATION_AI_API_KEY_ENV", "OPENAI_API_KEY").strip()
        self.classification_ai_model = config_values.get("CLASSIFICATION_AI_MODEL", "").strip()
        self.classification_ai_model_version = config_values.get("CLASSIFICATION_AI_MODEL_VERSION", "").strip()
        self.classification_ai_min_confidence = _parse_float(config_values.get("CLASSIFICATION_AI_MIN_CONFIDENCE"), 0.76)
        self.classification_ai_trigger_threshold = _parse_float(config_values.get("CLASSIFICATION_AI_TRIGGER_THRESHOLD"), 0.70)
        self.classification_ai_max_chars = _parse_int(config_values.get("CLASSIFICATION_AI_MAX_CHARS"), 3000)
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
    def _parse_csv_int_values(value: str | None) -> List[int]:
        if not value:
            return []

        values = []
        for configured_value in value.split(","):
            try:
                values.append(int(configured_value.strip()))
            except ValueError:
                continue

        return values

    @staticmethod
    def _resolve_path(value: str) -> Path:
        configured_path = Path(value)
        if configured_path.is_absolute():
            return configured_path

        return (SERVICE_ROOT / configured_path).resolve()

    @staticmethod
    def _resolve_stats_path(value: str) -> Path:
        configured_path = Path(value)
        if configured_path.is_absolute():
            return configured_path

        app_root = Path(os.environ.get("STATS_APP_ROOT", "")).resolve() if os.environ.get("STATS_APP_ROOT") else None
        if app_root:
            candidate = app_root / configured_path
            if candidate.exists():
                return candidate.resolve()

        repo_root_candidate = SERVICE_ROOT.parents[1] / configured_path
        if repo_root_candidate.exists():
            return repo_root_candidate.resolve()

        return (SERVICE_ROOT / configured_path).resolve()

    def _parse_paths(self, value: str | None) -> List[Path]:
        if not value:
            return []

        return [self._resolve_path(path_value.strip()) for path_value in value.split(";") if path_value.strip()]


settings = Settings()
# M5/M6 End
