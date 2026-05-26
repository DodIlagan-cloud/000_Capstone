"""M3/M4 - File Intake Module Start
Verifies merged intake behavior against a real PDF supplied through test data config.
M3/M4 End"""

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.main import app
from app.services.ingestion_service import reset_ingestion_store


@pytest.fixture()
def client_with_configured_storage(monkeypatch):
    reset_ingestion_store()
    configured_storage_root = Settings().storage_root
    monkeypatch.setattr("app.routes.ingestions.settings.storage_root", configured_storage_root)
    return TestClient(app)


def test_real_pdf_can_be_validated_ingested_saved_to_common_storage_and_retrieved(
    client_with_configured_storage,
    real_pdf_file,
):
    pdf_content = real_pdf_file.read_bytes()
    configured_storage_root = Settings().storage_root.resolve()

    validation_response = client_with_configured_storage.post(
        "/api/v1/files/validate",
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )
    validation_payload = validation_response.json()

    assert validation_response.status_code == 200
    assert validation_payload["status"] == "accepted"
    assert validation_payload["metadata"]["detected_mime_type"] == "application/pdf"
    assert validation_payload["metadata"]["size_bytes"] == real_pdf_file.stat().st_size

    ingestion_response = client_with_configured_storage.post(
        "/api/v1/ingestions",
        data={
            "validation_status": "accepted",
            "validation_sha256": validation_payload["metadata"]["sha256"],
            "detected_mime_type": validation_payload["metadata"]["detected_mime_type"],
            "source_type": "manual_upload",
            "source_id": "real-pdf-test-data",
            "submitted_by": "pytest-real-pdf",
            "idempotency_key": f"real-pdf-{validation_payload['metadata']['sha256']}",
        },
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )
    ingestion_payload = ingestion_response.json()

    assert ingestion_response.status_code == 200
    assert ingestion_payload["status"] == "queued"
    assert ingestion_payload["handoff"]["original_filename"] == real_pdf_file.name
    assert ingestion_payload["handoff"]["size_bytes"] == real_pdf_file.stat().st_size

    status_response = client_with_configured_storage.get(
        f"/api/v1/ingestions/{ingestion_payload['ingestion_id']}"
    )
    status_payload = status_response.json()
    handoff_file = Path(status_payload["handoff"]["content_reference"]).resolve()

    assert status_response.status_code == 200
    assert status_payload["status"] == "queued"
    assert status_payload["handoff"]["content_reference"]
    assert handoff_file.is_relative_to(configured_storage_root)
    assert handoff_file.stat().st_size == real_pdf_file.stat().st_size
