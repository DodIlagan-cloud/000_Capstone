"""M7 - Transaction Extraction Module Start
Verifies the transaction extraction JSON API.
M7 End"""


def test_extraction_endpoint_returns_candidates(client, generic_statement_table_text):
    response = client.post(
        "/api/v1/extractions",
        json={
            "parse_id": "parse_api_test",
            "document_type": "statement",
            "classification": {
                "document_type": "statement",
                "document_subtype": "credit_card_statement",
                "confidence": 0.9,
                "status": "classified",
            },
            "text": generic_statement_table_text,
            "document": {
                "original_filename": "statement.pdf",
                "sha256": "abc123",
            },
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["parse_id"] == "parse_api_test"
    assert payload["document"]["original_filename"] == "statement.pdf"
    assert payload["summary"]["transaction_candidate_count"] == 2
    assert payload["summary"]["financial_field_candidate_count"] >= 4
    assert payload["evaluation"]["document_type"] == "statement"


def test_extraction_endpoint_reports_missing_text(client):
    response = client.post(
        "/api/v1/extractions",
        json={
            "document_type": "receipt",
            "text": "",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "MISSING_TEXT"


def test_extraction_endpoint_accepts_m5_shaped_result(client, proof_of_payment_text):
    response = client.post(
        "/api/v1/extractions",
        json={
            "parse_id": "parse_image_ocr",
            "document": {
                "original_filename": "proof.jpg",
                "detected_mime_type": "image/jpeg",
                "sha256": "abc123",
            },
            "text": proof_of_payment_text,
            "pages": [{"page_number": 1, "text": proof_of_payment_text}],
            "metadata": {
                "extraction_method": "ocr",
                "ocr_engine": "tesseract",
            },
            "classification": {
                "document_type": "receipt",
                "document_subtype": "payment_terminal_receipt",
                "confidence": 0.8,
                "status": "classified",
            },
            "quality": {
                "text_length": len(proof_of_payment_text),
                "page_count": 1,
                "pages_processed": 1,
                "empty_page_count": 0,
                "low_text": False,
            },
            "findings": [],
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["parse_id"] == "parse_image_ocr"
    assert payload["document_type"] == "receipt"
    assert payload["summary"]["transaction_candidate_count"] == 1
    assert payload["summary"]["pages_processed"] == 1
