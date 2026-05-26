"""M3/M4 - File Intake Module Start
Tests ingestion endpoints in the merged validation and ingestion API.
M3/M4 End"""


def test_create_ingestion_accepts_validation_accepted_real_pdf(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()

    response = client.post(
        "/api/v1/ingestions",
        data={
            "validation_status": "accepted",
            "validation_sha256": "abc123",
            "detected_mime_type": "application/pdf",
            "source_type": "manual_upload",
            "submitted_by": "admin@example.test",
        },
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "queued"
    assert payload["source"]["source_type"] == "manual_upload"
    assert payload["validation"]["status"] == "accepted"
    assert payload["handoff"]["original_filename"] == real_pdf_file.name
    assert payload["handoff"]["size_bytes"] == real_pdf_file.stat().st_size
    assert payload["handoff"]["content_reference"]


def test_get_ingestion_status_returns_created_record_for_real_pdf(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()

    create_response = client.post(
        "/api/v1/ingestions",
        data={"validation_status": "accepted", "idempotency_key": "status-check"},
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )
    ingestion_id = create_response.json()["ingestion_id"]

    status_response = client.get(f"/api/v1/ingestions/{ingestion_id}")

    assert status_response.status_code == 200
    assert status_response.json()["ingestion_id"] == ingestion_id


def test_create_ingestion_rejects_failed_validation_result_for_real_pdf(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()

    response = client.post(
        "/api/v1/ingestions",
        data={"validation_status": "rejected"},
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    payload = response.json()
    codes = {finding["code"] for finding in payload["findings"]}

    assert response.status_code == 200
    assert payload["status"] == "rejected"
    assert "VALIDATION_NOT_ACCEPTED" in codes


def test_create_ingestion_returns_duplicate_for_idempotent_real_pdf_submission(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()
    request_data = {"validation_status": "accepted", "idempotency_key": "same-upload"}
    client.post(
        "/api/v1/ingestions",
        data=request_data,
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    response = client.post(
        "/api/v1/ingestions",
        data=request_data,
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    payload = response.json()
    codes = {finding["code"] for finding in payload["findings"]}

    assert response.status_code == 200
    assert payload["status"] == "duplicate"
    assert "DUPLICATE_SUBMISSION" in codes


def test_get_ingestion_status_returns_404_for_missing_record(client):
    response = client.get("/api/v1/ingestions/missing")

    assert response.status_code == 404
