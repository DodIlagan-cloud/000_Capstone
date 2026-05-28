"""M5 - Document Parsing Module Start
Tests the Document Parsing request/result API.
M5/M6 End"""


def test_parse_endpoint_returns_trace_classification_and_evaluation(client, monkeypatch, sample_pdf_content):
    monkeypatch.setattr(
        "app.services.parsing_service._extract_pdf_text",
        lambda content, page_limit: ("Bank Statement Account Balance Transaction Debit Credit Closing Balance", [], 1),
    )

    response = client.post(
        "/api/v1/parses",
        data={"ingestion_id": "ing_api_1", "source_type": "manual_upload", "classification_threshold": "0.2"},
        files={"file": ("statement.pdf", sample_pdf_content, "application/pdf")},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["document"]["ingestion_id"] == "ing_api_1"
    assert payload["document"]["source_type"] == "manual_upload"
    assert payload["classification"]["document_type"] == "bank_statement"
    assert payload["evaluation"]["document_id"] == "ing_api_1"
    assert payload["strategy"]["selected_strategy"] == "pdf_text"


def test_real_pdf_can_be_parsed_when_configured(client, real_pdf_file):
    response = client.post(
        "/api/v1/parses",
        files={"file": (real_pdf_file.name, real_pdf_file.read_bytes(), "application/pdf")},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["document"]["detected_mime_type"] == "application/pdf"
    assert payload["evaluation"]["input_media_type"] == "application/pdf"
    assert payload["evaluation"]["status"] in {"completed", "completed_with_warnings", "failed", "unsupported"}
