"""M12 - Email Ingestion Module Start
Provides FastAPI test client fixtures for the Email Ingestion Module.
M12 End"""

import base64
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "email-ingestion-module"
TEST_ACCESS_TOKEN_SECRET = "m12-test-access-token-secret-key-32-chars"

os.environ["ACCESS_TOKEN_SECRET_KEY"] = TEST_ACCESS_TOKEN_SECRET
os.environ["ACCESS_TOKEN_ALGORITHM"] = "HS256"
os.environ["STATS_INTERNAL_API_KEY"] = "m12-test-internal-api-key"


def _activate_module_root() -> None:
    for module_name in list(sys.modules):
        if module_name == "app" or module_name.startswith("app."):
            del sys.modules[module_name]
    module_root_path = str(MODULE_ROOT)
    if module_root_path in sys.path:
        sys.path.remove(module_root_path)
    sys.path.insert(0, module_root_path)


_activate_module_root()

from app.main import app


@pytest.fixture()
def client():
    _activate_module_root()
    from app.main import app as active_app

    return TestClient(active_app, headers={"Authorization": f"Bearer {_test_access_token()}"})


@pytest.fixture()
def unauthenticated_client():
    _activate_module_root()
    from app.main import app as active_app

    return TestClient(active_app)


@pytest.fixture(autouse=True)
def clear_email_sources():
    _activate_module_root()
    from app.services.secret_service import clear_cached_secrets
    from app.services.source_profile_service import clear_source_profiles

    clear_source_profiles()
    clear_cached_secrets()
    yield
    clear_source_profiles()
    clear_cached_secrets()


@pytest.fixture()
def run_ingestion_func():
    _activate_module_root()
    from app.services.ingestion_service import run_automated_email_ingestion

    return run_automated_email_ingestion


@pytest.fixture()
def ingestion_request_cls():
    _activate_module_root()
    from app.models.ingestion import AutomatedEmailIngestionRequest

    return AutomatedEmailIngestionRequest


@pytest.fixture()
def email_payload() -> dict[str, object]:
    content = b"%PDF-1.4\nsynthetic email fixture\n%%EOF"
    return {
        "source_id": "mailbox-primary",
        "authorization": {
            "provider": "synthetic",
            "account_id": "finance@example.test",
            "access_token_present": True,
        },
        "retrieval": {
            "mailbox_folder": "Inbox",
            "max_messages": 10,
        },
        "policy": {
            "deduplicate": True,
            "handoff_to_file_ingestion": False,
            "dry_run": True,
        },
        "messages": [
            {
                "message_id": "message-001",
                "internet_message_id": "<message-001@example.test>",
                "sender": "statements@example.test",
                "subject": "June statement",
                "received_at": "2026-06-17T08:30:00Z",
                "attachments": [
                    {
                        "attachment_id": "attachment-001",
                        "filename": "statement.pdf",
                        "content_type": "application/pdf",
                        "size_bytes": len(content),
                        "content_base64": base64.b64encode(content).decode("ascii"),
                    }
                ],
            }
        ],
    }


def _test_access_token(subject: str = "test-user") -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": subject, "exp": int(expires_at.timestamp())}
    signing_input = (
        f"{_b64encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64encode(json.dumps(payload, separators=(',', ':')).encode('utf-8'))}"
    )
    signature = hmac.new(TEST_ACCESS_TOKEN_SECRET.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")
