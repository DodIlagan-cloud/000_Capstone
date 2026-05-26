"""Tests for the ingest endpoint."""

from fastapi.testclient import TestClient
from app.main import app
import io

client = TestClient(app)


def test_ingest_invalid_file_type():
    """Test ingest endpoint with invalid file type."""
    response = client.post(
        "/api/v1/ingest",
        files={"file": ("test.txt", io.BytesIO(b"not a pdf"), "text/plain")}
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data


def test_ingest_missing_file():
    """Test ingest endpoint without file."""
    response = client.post("/api/v1/ingest")
    assert response.status_code == 422
