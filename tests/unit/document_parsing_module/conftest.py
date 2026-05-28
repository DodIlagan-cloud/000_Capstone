"""M5 - Document Parsing Module Start
Provides FastAPI test client fixtures for the Document Parsing Module.
M5/M6 End"""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "document-parsing-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from app.main import app


def _real_pdf_file() -> Path:
    test_data_dir = os.environ.get("STATS_PARSING_TESTDATA_DIR") or os.environ.get("STATS_TESTDATA_DIR")
    if not test_data_dir:
        pytest.fail("Set STATS_PARSING_TESTDATA_DIR or STATS_TESTDATA_DIR before running real document parsing tests.")

    data_root = Path(test_data_dir)
    if not data_root.exists():
        pytest.fail(f"Configured real document test data directory does not exist: {data_root}")

    pdf_files = sorted(data_root.glob("*.pdf"))
    if not pdf_files:
        pytest.fail(f"No PDF files found in configured real document test data directory: {data_root}")

    return pdf_files[0]


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def real_pdf_file() -> Path:
    return _real_pdf_file()


@pytest.fixture()
def sample_pdf_content() -> bytes:
    return _real_pdf_file().read_bytes()
