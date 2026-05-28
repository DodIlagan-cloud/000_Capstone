"""Merged file intake evidence script.

Runs direct HTTP checks against the local merged validation and ingestion API.
"""

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tests/scripts" / "common"))
from test_config import configured_url

BASE_URL = configured_url(__file__, "fileIntakeBaseUrl")


def request_json(url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = response.read().decode("utf-8")
        print(f"{request.get_method()} {url} -> HTTP {response.status}")
        return json.loads(payload)


def multipart_body(fields: dict[str, str], file_field: str, filename: str, content_type: str, content: bytes):
    boundary = f"----StatsEvidence{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                f"{value}\r\n".encode(),
            ]
        )

    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            (
                f'Content-Disposition: form-data; name="{file_field}"; '
                f'filename="{filename}"\r\n'
            ).encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            content,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )

    return b"".join(chunks), {"Content-Type": f"multipart/form-data; boundary={boundary}"}


def main() -> int:
    print("Merged File Validation and Ingestion Module evidence check")
    print(f"Service URL: {BASE_URL}")

    health = request_json(f"{BASE_URL}/health")
    assert health["status"] == "healthy"

    file_content = b"%PDF-1.7\nEvidence file"
    validate_body, validate_headers = multipart_body(
        fields={},
        file_field="file",
        filename="evidence.pdf",
        content_type="application/pdf",
        content=file_content,
    )
    validation = request_json(
        f"{BASE_URL}/api/v1/files/validate",
        data=validate_body,
        headers=validate_headers,
    )
    assert validation["status"] == "accepted"
    sha256 = validation["metadata"]["sha256"]
    print(f"Validation accepted with sha256={sha256}")

    ingest_body, ingest_headers = multipart_body(
        fields={
            "validation_status": "accepted",
            "validation_sha256": sha256,
            "detected_mime_type": "application/pdf",
            "source_type": "manual_upload",
            "submitted_by": "evidence-runner",
            "idempotency_key": f"evidence-{uuid.uuid4()}",
        },
        file_field="file",
        filename="evidence.pdf",
        content_type="application/pdf",
        content=file_content,
    )
    ingestion = request_json(
        f"{BASE_URL}/api/v1/ingestions",
        data=ingest_body,
        headers=ingest_headers,
    )
    assert ingestion["status"] == "queued"
    ingestion_id = ingestion["ingestion_id"]
    print(f"Ingestion queued with ingestion_id={ingestion_id}")

    status = request_json(f"{BASE_URL}/api/v1/ingestions/{ingestion_id}")
    assert status["ingestion_id"] == ingestion_id
    assert status["status"] == "queued"
    assert status["handoff"]["content_reference"]
    print(f"Handoff reference: {status['handoff']['content_reference']}")

    print("Result: PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, urllib.error.URLError) as exc:
        print(f"Result: FAILED ({exc})")
        raise
