"""M3 - File Validation Module Start
Tests the File Validation request/result API.
M3 End"""


def test_validate_file_endpoint_accepts_real_pdf(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()

    response = client.post(
        "/api/v1/files/validate",
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "accepted"
    assert payload["metadata"]["detected_mime_type"] == "application/pdf"
    assert payload["metadata"]["extension"] == ".pdf"
    assert payload["metadata"]["size_bytes"] == real_pdf_file.stat().st_size


def test_validate_file_endpoint_applies_request_policy_to_real_pdf(client, real_pdf_file):
    pdf_content = real_pdf_file.read_bytes()

    response = client.post(
        "/api/v1/files/validate",
        data={"max_size_bytes": "4"},
        files={"file": (real_pdf_file.name, pdf_content, "application/pdf")},
    )

    payload = response.json()
    codes = {finding["code"] for finding in payload["findings"]}

    assert response.status_code == 200
    assert payload["status"] == "rejected"
    assert "FILE_TOO_LARGE" in codes
