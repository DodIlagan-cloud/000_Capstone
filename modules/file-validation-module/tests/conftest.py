"""M3 - File Validation Module Start
Provides FastAPI test client fixtures for the File Validation Module.
M3 End"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from app.main import app


@pytest.fixture()
def client():
    return TestClient(app)
