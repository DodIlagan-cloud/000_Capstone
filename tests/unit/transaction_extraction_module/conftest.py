"""M7 - Transaction Extraction Module Start
Provides FastAPI test client fixtures for the Transaction Extraction Module.
M7 End"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "transaction-extraction-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def bank_statement_text() -> str:
    return "\n".join(
        [
            "STATEMENT DATE NOVEMBER 07, 2023",
            "PAYMENT DUE DATE NOVEMBER 28, 2023",
            "TOTAL AMOUNT DUE 46,320.12",
            "MINIMUM AMOUNT DUE 1,612.08",
            "Nov 02 2023 Payment Credits and Rebates 77,803.97",
            "Nov 05 2023 Purchase Grocery Store 2,345.67",
        ]
    )


@pytest.fixture()
def proof_of_payment_text() -> str:
    return "\n".join(
        [
            "Transfer successful!",
            "Thursday, Jan 08 2026; 01:20:34 PM (GMT +8)",
            "Confirmation No. 32110001",
            "Transfer to ACQUA EDEN RE",
            "Transfer amount PHP 17,274.97",
            "Transfer from CHECKING 1234",
        ]
    )
