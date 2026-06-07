"""M3 - File Validation Module Start
Provides FastAPI test client fixtures for the File Validation Module.
M3 End"""

import sys
import os
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "file-validation-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from app.main import app
from app.services.ingestion_service import reset_ingestion_store


@pytest.fixture()
def client(tmp_path, monkeypatch):
    reset_ingestion_store()
    monkeypatch.setattr("app.routes.ingestions.settings.storage_root", tmp_path / "intake")
    monkeypatch.setattr("app.routes.ingestions.settings.stats_storage_provider", "LocalFileSystem")
    return TestClient(app)


@pytest.fixture()
def real_pdf_file() -> Path:
    test_data_dir = os.environ.get("STATS_TESTDATA_DIR")
    if not test_data_dir:
        pytest.fail("Set STATS_TESTDATA_DIR to the shared real application test-data directory.")

    data_root = Path(test_data_dir)
    if not data_root.exists():
        pytest.fail(f"Configured STATS_TESTDATA_DIR does not exist: {data_root}")

    pdf_files = sorted(data_root.glob("*.pdf"))
    if not pdf_files:
        pytest.fail(f"No real PDF files found in STATS_TESTDATA_DIR: {data_root}")

    return pdf_files[0]
