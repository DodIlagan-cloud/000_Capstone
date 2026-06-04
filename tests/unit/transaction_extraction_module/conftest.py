"""M7 - Transaction Extraction Module Start
Provides FastAPI test client fixtures for the Transaction Extraction Module.
M7 End"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "transaction-extraction-module"
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
def extraction_request_cls():
    _activate_module_root()
    from app.models.extraction import TransactionExtractionRequest

    return TransactionExtractionRequest


@pytest.fixture()
def extract_transactions_func():
    _activate_module_root()
    from app.services.extraction_service import extract_transactions

    return extract_transactions


@pytest.fixture()
def client():
    _activate_module_root()
    from app.main import app as active_app

    return TestClient(active_app)


@pytest.fixture()
def generic_statement_table_text() -> str:
    return "\n".join(
        [
            "STATEMENT DATE NOVEMBER 07, 2023",
            "PAYMENT DUE DATE NOVEMBER 28, 2023",
            "TOTAL AMOUNT DUE 46,320.12",
            "MINIMUM AMOUNT DUE 1,612.08",
            "Nov 02 2023 Payment Credits and Rebates 77,803.97",
            "Nov 05 2023 Purchase General Store 2,345.67",
        ]
    )


@pytest.fixture()
def generic_split_statement_table_text() -> str:
    return "\n".join(
        [
            "STATEMENT DATE NOVEMBER 07, 2023",
            "Transaction",
            "Post Date",
            "Description",
            "Amount",
            "Date",
            "October 12",
            "October 12",
            "Payment - Thank You",
            "-77,803.97",
            "Finance Charge",
            "0.00",
            "Previous Balance",
            "77,803.97",
            "Installment Amortization:",
            "November 7",
            "November 7",
            "Keds - Sm Megamall",
            "MA: 02/03",
            "1,498.50",
            "November 7",
            "November 7",
            "Credit-To-Cash 2-Reg",
            ": 34/36",
            "5,025.83",
            "S.I.P. BALANCE SUMMARY",
            "Transaction Date",
            "Last Payment Date",
            "Description",
            "Purchase Amount",
            "Remaining Balance",
        ]
    )


@pytest.fixture()
def generic_combined_statement_table_text() -> str:
    return "\n".join(
        [
            "STATEMENT DATE NOVEMBER 07, 2023",
            "Transaction Post Date Description Amount",
            "Date",
            "October 12 October 12 Payment - Thank You -77,803.97",
            "Credit Limit 989,000.00",
            "November 7 November 7 Credit-To-Cash 2-Reg : 34/36 5,025.83",
            "November 7 November 7 Credit-To-Cash 4 - Reg : 15/36 12,559.94",
            "S.I.P. BALANCE SUMMARY",
        ]
    )


@pytest.fixture()
def flattened_credit_card_statement_ocr_text() -> str:
    return (
        "Statement From 13 NOV 2023 to 12 DEC 2023 "
        "POST TRAN DATE DATE DESCRIPTION AMOUNT(PHP) "
        "14 Nov 11 Nov DIN TAI FUNG MANDALUYONG PH 3,609.62 "
        "13 Nov 13 Nov CARD MEMBERSHIP FEE REVERSAL 2,500.00CR "
        "15 Nov 13 Nov HUMAN NATURE LIPA BATANGAS PH 1,019.50 "
        "21 Nov 19 Nov PAID THRU ONLINE BANKING 61,586.10CR "
        "Credit Limit PHP 192,000.00 Minimum Amount Due PHP 2,591.95"
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


@pytest.fixture()
def single_line_invoice_ocr_text() -> str:
    return (
        "Invoice AwanuiLabs Auckland Issued: 18/04/2026 09:36:20 "
        "Tax Invoice no.: 384590 CC CRE - Creatinine $25.00 "
        "Total GST $29.61 Payment History Paid 18/04/2026 09:36:20 - EFTPOS"
    )


@pytest.fixture()
def single_line_pharmacy_receipt_ocr_text() -> str:
    return (
        "3 Kings Plaza Pharmacy 18-May-2026 11:35am "
        "Product Unit Qty Total Rx Item $15.70 $15.70 "
        "Tax invoice: Total $94.25 Includes GST of $12.29 "
        "EFTPOS PURCHASE NZD94. 25 TOTAL NZD94.25 APPROVED"
    )


@pytest.fixture()
def single_line_card_receipt_ocr_text() -> str:
    return (
        "Awanui Mt Wellington TRAN CREDIT RRN 16693501018 "
        "Visa Credit PURCHASE > 1714. 227.00 NZ$ 227,00 APPROVED"
    )


@pytest.fixture()
def generic_statement_summary_text() -> str:
    return (
        "Credit Cards Statement of Account Prepared for Reference No. 754A7760-3 "
        "CUSTOMER NUMBER 020100-3-30-7760754 STATEMENT DATE NOVEMBER 07, 2023 "
        "PAYMENT DUE DATE NOVEMBER 28, 2023 CREDIT LIMIT 989,000.00 "
        "TOTAL AMOUNT DUE 46,320.12 MINIMUM AMOUNT DUE 1,612.08 "
        "Gold 77,803.97 77,803.97 1,181.76 45,138.36 0.00 0.00 46,920.12 "
        "Past Due Amount 0.00 Total Outstanding Balance 1,041,386.74 "
        "Important Advisory: Finance Charge or Nominal Interest Rate 2% 3%"
    )
