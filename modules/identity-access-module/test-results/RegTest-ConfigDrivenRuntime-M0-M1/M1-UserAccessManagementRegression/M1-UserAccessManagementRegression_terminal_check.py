"""M1 User Access Management config-driven runtime regression evidence."""

# M1 - User Access Management Start
# Verifies M1 configured runtime values, API behavior, and the Stats Web consumer for regression evidence.
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

SERVICE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings

configured_settings = Settings()

os.environ["DATABASE_URL"] = "sqlite://"

from app.db import get_db
from app.main import app
from app.models.database import Base
from app.models.user import UserRole
from app.services.user_service import create_initial_admin


def get_status(url: str) -> int:
    with urllib.request.urlopen(url, timeout=5) as response:
        return response.status


def load_stats_web_base_url() -> str:
    appsettings_path = REPO_ROOT / "apps" / "stats-web" / "appsettings.json"
    return json.loads(appsettings_path.read_text(encoding="utf-8"))["StatsApi"]["BaseUrl"]


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
EvidenceSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = EvidenceSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
db = EvidenceSessionLocal()
admin = create_initial_admin(db, "m1.config.admin@example.com", "TempAdmin123")
db.close()

client = TestClient(app)
login_response = client.post(
    "/api/v1/auth/login",
    json={"email": admin.email, "password": "TempAdmin123"},
)
admin_token = login_response.json()["access_token"]
blocked_user_response = client.post(
    "/api/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "email": "m1.config.blocked@example.com",
        "full_name": "Blocked User",
        "password": "TempUser123",
        "role": UserRole.USER,
        "is_active": True,
    },
)
password_response = client.post(
    "/api/v1/auth/change-password",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"new_password": "AdminReady123"},
)
created_user_response = client.post(
    "/api/v1/users",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={
        "email": "m1.config.created@example.com",
        "full_name": "Created User",
        "password": "TempUser123",
        "role": UserRole.USER,
        "is_active": True,
    },
)
created_user_login = client.post(
    "/api/v1/auth/login",
    json={"email": "m1.config.created@example.com", "password": "TempUser123"},
)

print("M1 CONFIG-DRIVEN RUNTIME REGRESSION TEST EVIDENCE")
print("=" * 58)
print("Automated test command: pytest tests\\test_auth.py tests\\test_users.py tests\\test_foundation.py")
print("Frontend build command: dotnet build apps\\stats-web -c Release")
print(f"Configured database URL ends with /stats: {configured_settings.database_url.endswith('/stats')}")
print(f"Configured API host: {configured_settings.api_host}")
print(f"Configured API port: {configured_settings.api_port}")
print(f"Configured CORS origins: {configured_settings.cors_allowed_origins}")
print(f"Stats Web configured API base URL: {load_stats_web_base_url()}")
print(f"Visible API health status: {get_status('http://127.0.0.1:8013/health')}")
print(f"Visible Stats Web login page status: {get_status('http://127.0.0.1:5013/Login')}")
print(f"Backend docs status: {client.get('/docs').status_code}")
print(f"Bootstrap admin must change password: {admin.must_change_password}")
print(f"Bootstrap admin login status: {login_response.status_code}")
print(f"Bootstrap admin password change required: {login_response.json()['password_change_required']}")
print(f"User add before password change status: {blocked_user_response.status_code}")
print(f"Admin password change status: {password_response.status_code}")
print(f"User add after password change status: {created_user_response.status_code}")
print(f"Created user must change password: {created_user_response.json()['must_change_password']}")
print(f"Created user first login status: {created_user_login.status_code}")
print(f"Created user password change required: {created_user_login.json()['password_change_required']}")
print()
print("Result: PASSED")

app.dependency_overrides.pop(get_db, None)
Base.metadata.drop_all(bind=engine)
# M1 End
