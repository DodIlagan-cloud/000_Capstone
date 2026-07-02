"""M12 - Email Ingestion Module Start
Automated pipeline HTTP clients.

Thin httpx wrappers over the existing Stats module endpoints. These are the only
component that imports httpx, so the orchestration core and request builders stay
dependency-free and unit-testable. Every call carries the internal service key.

Endpoints consumed (all pre-existing; none modified):
- POST   {stats_data}/api/v1/processing-jobs
- PATCH  {stats_data}/api/v1/processing-jobs/{job_id}
- GET    {stats_data}/api/v1/admin/recognition-settings/active
- POST   {document_parsing}/api/v1/parses                (multipart)
- POST   {transaction_extraction}/api/v1/extractions
- POST   {data_validation}/api/v1/validations
- POST   {stats_data}/api/v1/transactions/batches        (save to database)

The save persists the M8 validation result via the M9 endpoint with a system identity
(process-to-database). It is NOT fully governed auto-save yet - the automated save
takes the unreviewed path so M9 governs it (pending recognition suggestions +
review_items); full automated governance is tracked in the M12 completion plan.
M12 End"""

import httpx

from app.pipeline.config import OrchestratorSettings
from app.pipeline.models import PipelineRunRequest
from app.pipeline.request_builders import build_extraction_request, build_validation_request


class PipelineClients:
    def __init__(self, settings: OrchestratorSettings, http: "httpx.Client | None" = None) -> None:
        # Every database-ingest call is server-to-server and the file-intake readback
        # requires the internal key, so fail fast on a clear config error rather than
        # letting calls 401 downstream.
        if not settings.internal_api_key:
            raise RuntimeError(
                "STATS_INTERNAL_API_KEY is required for automated database ingestion "
                "(process-imported / scheduled ingest)."
            )
        self.settings = settings
        self._owns_http = http is None
        self.http = http or httpx.Client(timeout=settings.request_timeout_seconds)

    def close(self) -> None:
        # Release pooled connections; only closes a client this instance created.
        if self._owns_http:
            self.http.close()

    def _headers(self) -> dict[str, str]:
        if not self.settings.internal_api_key:
            return {}
        return {"X-Stats-Internal-Key": self.settings.internal_api_key}

    def fetch_content(self, request: PipelineRunRequest) -> bytes:
        # Read back the stored original bytes for an already-imported file from M3/M4
        # intake. Used when the trigger does not carry inline content_base64.
        response = self.http.get(
            f"{self.settings.file_intake_base_url}/api/v1/ingestions/{request.ingestion_id}/content",
            headers=self._headers(),
        )
        response.raise_for_status()
        return response.content

    def create_job(self, request: PipelineRunRequest) -> str:
        response = self.http.post(
            f"{self.settings.stats_data_base_url}/api/v1/processing-jobs",
            headers=self._headers(),
            json={
                "ingestion_id": request.ingestion_id,
                "uploaded_by_user_id": request.uploaded_by_user_id or self.settings.automated_uploaded_by_user_id,
                "original_filename": request.original_filename,
                "source_type": request.source_type,
                "source_id": request.source_id,
                "sha256": request.sha256,
                "message": "Automated ingestion received. Stats is preparing to read it.",
            },
        )
        response.raise_for_status()
        job_id = (response.json() or {}).get("job_id")
        if not job_id:
            raise RuntimeError("Stats Data did not return a job_id for the processing job.")
        return job_id

    def update_job(self, job_id: str, **fields) -> None:
        payload = {key: value for key, value in fields.items() if value is not None}
        response = self.http.patch(
            f"{self.settings.stats_data_base_url}/api/v1/processing-jobs/{job_id}",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()

    def parse(self, content: bytes, request: PipelineRunRequest) -> dict:
        data = {
            "ingestion_id": request.ingestion_id,
            "source_type": request.source_type,
            "source_id": request.source_id or "",
            "sha256": request.sha256 or "",
            "allow_ocr_fallback": self.settings.allow_ocr_fallback,
            "classification_threshold": self.settings.classification_threshold,
        }
        files = {"file": (request.original_filename, content, request.content_type or "application/pdf")}
        response = self.http.post(
            f"{self.settings.document_parsing_base_url}/api/v1/parses",
            headers=self._headers(),
            data=data,
            files=files,
        )
        response.raise_for_status()
        return response.json()

    def extract(self, parse_result: dict) -> dict:
        response = self.http.post(
            f"{self.settings.transaction_extraction_base_url}/api/v1/extractions",
            headers=self._headers(),
            json=build_extraction_request(parse_result),
        )
        response.raise_for_status()
        return response.json()

    def fetch_recognition_context(self) -> dict:
        try:
            response = self.http.get(
                f"{self.settings.stats_data_base_url}/api/v1/admin/recognition-settings/active",
                headers=self._headers(),
            )
            if response.status_code >= 400:
                return {}
            return (response.json() or {}).get("recognition_context") or {}
        except Exception:  # noqa: BLE001 - recognition context is best-effort, like the manual flow.
            return {}

    def validate(self, extraction_result: dict, recognition_context: dict) -> dict:
        response = self.http.post(
            f"{self.settings.data_validation_base_url}/api/v1/validations",
            headers=self._headers(),
            json=build_validation_request(extraction_result, recognition_context),
        )
        response.raise_for_status()
        return response.json()

    def save(self, validation_result: dict, request: PipelineRunRequest, job_id: str) -> dict:
        response = self.http.post(
            f"{self.settings.stats_data_base_url}/api/v1/transactions/batches",
            headers=self._headers(),
            json={
                "validation_result": validation_result,
                "uploaded_by_user_id": request.uploaded_by_user_id or self.settings.automated_uploaded_by_user_id,
                "saved_by_user_id": self.settings.automated_saved_by_user_id,
                "storage_reference": request.storage_reference,
                "processing_job_id": job_id,
            },
        )
        response.raise_for_status()
        return response.json()
