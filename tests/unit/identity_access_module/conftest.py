"""M1 - User Access Management Start
Provides shared test setup for the standalone Identity Access Module.
M1 End"""

# M1 - User Access Management Start
# Imports environment support for the Module 1 test database override.
import os
import sys
from pathlib import Path
# M1 End

from fastapi.testclient import TestClient
import pytest
# M1 - User Access Management Start
# Imports SQLAlchemy helpers for isolated Module 1 user access tests.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
# M1 End

# M1 - User Access Management Start
# Forces tests to use local SQLite instead of requiring a PostgreSQL service.
MODULE_ROOT = Path(__file__).resolve().parents[3] / "modules" / "identity-access-module"
for module_name in list(sys.modules):
    if module_name == "app" or module_name.startswith("app."):
        del sys.modules[module_name]
sys.path.insert(0, str(MODULE_ROOT))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DATABASE_PROVIDER"] = "SQLite"
# M1 End

# M1 - User Access Management Start
# Imports Module 1 database and user helpers for authentication fixtures.
from app.db import get_db
# M1 End
from app.main import app
# M1 - User Access Management Start
# Imports Module 1 database and user helpers for authentication fixtures.
from app.models.database import Base
from app.models.user import UserCreate, UserRole
from app.services.user_service import change_password, create_user
# M1 End

# M1 - User Access Management Start
# Builds an isolated test database and reusable authenticated users.
TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def test_database():
    """Create a clean test database for each test."""
    Base.metadata.create_all(bind=engine)
    try:
        yield
    finally:
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(test_database):
    """Create a test database session."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_user(db_session):
    """Create an active administrator."""
    user = create_user(
        db_session,
        UserCreate(
            email="admin@example.com",
            full_name="Admin User",
            password="Admin123",
            role=UserRole.ADMIN,
        ),
    )
    return change_password(db_session, user, "Admin123")


@pytest.fixture
def standard_user(db_session):
    """Create an active standard user."""
    user = create_user(
        db_session,
        UserCreate(
            email="user@example.com",
            full_name="Standard User",
            password="User1234",
            role=UserRole.USER,
        ),
    )
    return change_password(db_session, user, "User1234")


@pytest.fixture
def inactive_user(db_session):
    """Create an inactive standard user."""
    user = create_user(
        db_session,
        UserCreate(
            email="inactive@example.com",
            full_name="Inactive User",
            password="Inactive123",
            role=UserRole.USER,
            is_active=False,
        ),
    )
    return change_password(db_session, user, "Inactive123")


def override_get_db():
    """Override application database dependency for tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
# M1 End


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client."""
    return TestClient(app)
