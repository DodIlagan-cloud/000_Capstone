"""M8 - Data Validation Module Start
Provides FastAPI test client fixtures for the Data Validation Module.
M8 End"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "data-validation-module"
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
def module_app():
    _activate_module_root()
    from app.main import app as active_app

    return active_app


@pytest.fixture()
def settings_cls():
    _activate_module_root()
    from app.config import Settings

    return Settings


@pytest.fixture()
def validation_request_cls():
    _activate_module_root()
    from app.models.validation import DataValidationRequest

    return DataValidationRequest


@pytest.fixture()
def validate_data_func():
    _activate_module_root()
    from app.services.validation_service import validate_data

    return validate_data


@pytest.fixture()
def client():
    _activate_module_root()
    from app.main import app as active_app

    return TestClient(active_app)


@pytest.fixture()
def m7_candidates() -> dict[str, object]:
    return {
        "extraction_id": "extract_test",
        "parse_id": "parse_test",
        "document_type": "statement",
        "document": {
            "original_filename": "statement.pdf",
            "sha256": "abc123",
        },
        "transaction_candidates": [
            {
                "candidate_id": "txn_0001",
                "date_text": "Nov 02 2023",
                "description": "Payment Credits and Rebates",
                "amount": 77803.97,
                "currency": "PHP",
                "direction": "credit",
                "source": {"page_number": 1, "line_number": 5, "text": "Nov 02 2023 Payment Credits and Rebates 77,803.97"},
                "confidence": 0.92,
                "reason_codes": ["AMOUNT_DETECTED", "DATE_DETECTED"],
            },
            {
                "candidate_id": "txn_0002",
                "date_text": "Nov 05 2023",
                "description": "Purchase General Store",
                "amount": 2345.67,
                "currency": "PHP",
                "direction": "debit",
                "source": {"page_number": 1, "line_number": 6, "text": "Nov 05 2023 Purchase General Store 2,345.67"},
                "confidence": 0.88,
                "reason_codes": ["AMOUNT_DETECTED", "DATE_DETECTED"],
            },
        ],
        "financial_field_candidates": [
            {
                "field_name": "total_amount_due",
                "value_text": "46,320.12",
                "normalized_value": "46320.12",
                "currency": "PHP",
                "source": {"page_number": 1, "line_number": 3, "text": "TOTAL AMOUNT DUE 46,320.12"},
                "confidence": 0.86,
                "reason_codes": ["FIELD_LABEL_DETECTED", "AMOUNT_DETECTED"],
            }
        ],
    }
