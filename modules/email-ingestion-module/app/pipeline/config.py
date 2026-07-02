"""M12 - Email Ingestion Module Start
Automated pipeline configuration.

Reads downstream module base URLs and the internal service key from the environment.
The orchestrator authenticates to each Stats module with the internal API key, the
same server-to-server trust boundary M12 uses for its file-intake handoff.
M12 End"""

import os
from dataclasses import dataclass
from typing import Mapping, Optional


def _clean(url: Optional[str]) -> str:
    return (url or "").rstrip("/")


@dataclass
class OrchestratorSettings:
    stats_data_base_url: str
    document_parsing_base_url: str
    transaction_extraction_base_url: str
    data_validation_base_url: str
    file_intake_base_url: str
    internal_api_key: Optional[str]
    automated_uploaded_by_user_id: str
    automated_saved_by_user_id: str
    allow_ocr_fallback: str
    classification_threshold: str
    request_timeout_seconds: float


def load_settings(env: Optional[Mapping[str, str]] = None) -> OrchestratorSettings:
    env = env if env is not None else os.environ
    return OrchestratorSettings(
        stats_data_base_url=_clean(env.get("STATS_DATA_BASE_URL")),
        document_parsing_base_url=_clean(env.get("DOCUMENT_PARSING_BASE_URL")),
        transaction_extraction_base_url=_clean(env.get("TRANSACTION_EXTRACTION_BASE_URL")),
        data_validation_base_url=_clean(env.get("DATA_VALIDATION_BASE_URL")),
        # M3/M4 file intake, reused to read back stored bytes for already-imported
        # files. Same base URL M12 uses for handoff (FILE_INGESTION_BASE_URL).
        file_intake_base_url=_clean(env.get("FILE_INGESTION_BASE_URL")),
        internal_api_key=env.get("STATS_INTERNAL_API_KEY"),
        # System identities mark automated saves so provenance is auditable and
        # distinct from user-reviewed saves.
        automated_uploaded_by_user_id=env.get("AUTOMATED_UPLOADED_BY_USER_ID", "system-email-ingestion"),
        automated_saved_by_user_id=env.get("AUTOMATED_SAVED_BY_USER_ID", "system-email-automation"),
        allow_ocr_fallback=env.get("AUTOMATED_ALLOW_OCR_FALLBACK", "true"),
        classification_threshold=env.get("AUTOMATED_CLASSIFICATION_THRESHOLD", "0.1"),
        request_timeout_seconds=float(env.get("AUTOMATED_PIPELINE_TIMEOUT_SECONDS", "120")),
    )
