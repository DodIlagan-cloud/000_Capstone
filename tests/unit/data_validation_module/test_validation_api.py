"""M8 - Data Validation Module Start
Verifies the data validation JSON API.
M8 End"""


def test_validation_endpoint_returns_normalized_records(client, extraction_candidates):
    response = client.post("/api/v1/validations", json=extraction_candidates)
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["extraction_id"] == "extract_test"
    assert payload["parse_id"] == "parse_test"
    assert payload["summary"]["normalized_record_count"] == 2
    assert payload["summary"]["valid_record_count"] == 2
    assert payload["summary"]["debit_total"] == 2345.67
    assert payload["summary"]["credit_total"] == 77803.97
    assert payload["summary"]["net_total"] == 75458.3
    assert payload["normalized_records"][0]["transaction_date"] == "2023-11-02"
    assert payload["financial_fields"][0]["field_name"] == "total_amount_due"


def test_validation_endpoint_reports_missing_candidates(client):
    response = client.post(
        "/api/v1/validations",
        json={"document_type": "receipt", "transaction_candidates": [], "financial_field_candidates": []},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "failed"
    assert payload["findings"][0]["code"] == "MISSING_CANDIDATES"


def test_validation_endpoint_accepts_extraction_shape_with_upstream_findings(client, extraction_candidates):
    extraction_candidates["findings"] = [
        {
            "code": "LOW_CONFIDENCE_EXTRACTION",
            "severity": "warning",
            "message": "One or more extraction candidates are below the configured confidence threshold.",
        }
    ]

    response = client.post("/api/v1/validations", json=extraction_candidates)
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed_with_warnings"
    assert payload["evaluation"]["finding_counts"]["LOW_CONFIDENCE_EXTRACTION"] == 1
