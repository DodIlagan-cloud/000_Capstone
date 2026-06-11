"""M5 - Document Parsing Module Start
Provides FastAPI test client fixtures for the Document Parsing Module.
M5/M6 End"""

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "document-parsing-module"
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


def _configured_test_data_dir() -> Path:
    test_data_dir = os.environ.get("STATS_PARSING_TESTDATA_DIR") or os.environ.get("STATS_TESTDATA_DIR")
    if not test_data_dir:
        pytest.skip(
            "Real document parsing fixtures are not configured for this host-side diagnostic run. "
            "Official M5 acceptance runs inside stats-runtime with /app/tests/input configured."
        )
    return Path(test_data_dir)


def _real_pdf_file() -> Path:
    data_root = _configured_test_data_dir()
    if not data_root.exists():
        pytest.fail(f"Configured real document test data directory does not exist: {data_root}")

    pdf_files = sorted(data_root.glob("*.pdf"))
    if not pdf_files:
        pytest.fail(f"No PDF files found in configured real document test data directory: {data_root}")

    return pdf_files[0]


def _input_file(filename: str) -> Path:
    path = _configured_test_data_dir() / filename
    if not path.exists():
        pytest.fail(f"Required real document test input does not exist: {path}")
    return path


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def real_pdf_file() -> Path:
    return _real_pdf_file()


@pytest.fixture()
def sample_pdf_content() -> bytes:
    return _real_pdf_file().read_bytes()


@pytest.fixture()
def input_file():
    return _input_file
