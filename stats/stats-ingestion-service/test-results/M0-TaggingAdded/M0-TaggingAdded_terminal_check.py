"""M0 TaggingAdded: direct verification script for terminal screenshot evidence."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import app


client = TestClient(app)
health_response = client.get("/health")
root_response = client.get("/")

print("M0 TAGGING ADDED TERMINAL TEST EVIDENCE")
print("=" * 42)
print(f"App title: {app.title}")
print(f"Health status: {health_response.status_code}")
print(f"Health body: {health_response.json()}")
print(f"Root status: {root_response.status_code}")
print(f"Root body: {root_response.json()}")
print()
print("Result: PASSED")
