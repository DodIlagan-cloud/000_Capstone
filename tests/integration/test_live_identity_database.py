"""M1/M3 Regression Start
Verifies Identity Access against the configured live Stats database without dropping tables.
M1/M3 Regression End"""

import os
import sys
import uuid
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_MODULE_ROOT = REPO_ROOT / "modules" / "identity-access-module"
sys.path.insert(0, str(IDENTITY_MODULE_ROOT))

from app.db import SessionLocal, init_db  # noqa: E402
from app.models.user import LoginRequest, User, UserCreate, UserRole  # noqa: E402
from app.services.auth_service import authenticate_user  # noqa: E402
from app.services.user_service import change_password, create_user, get_user_by_email  # noqa: E402


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_DATABASE_TESTS") != "1",
    reason="Set RUN_LIVE_DATABASE_TESTS=1 to run against the configured live Stats database.",
)


def test_live_stats_database_can_create_authenticate_and_cleanup_test_user():
    """Use the actual configured database while deleting only this test's user record."""
    init_db()
    email = f"live-db-test-{uuid.uuid4().hex}@example.com"
    initial_password = "LiveDb123"
    final_password = "LiveDb456"
    db = SessionLocal()

    try:
        existing_count = db.query(User).count()
        user = create_user(
            db,
            UserCreate(
                email=email,
                full_name="Live Database Test",
                password=initial_password,
                role=UserRole.USER,
            ),
        )

        assert user.id
        assert user.email == email
        assert user.must_change_password is True
        assert db.query(User).count() == existing_count + 1

        user = change_password(db, user, final_password)
        authenticated = authenticate_user(
            db,
            LoginRequest(email=email, password=final_password),
        )

        assert user.must_change_password is False
        assert authenticated.id == user.id
        assert authenticated.last_login_at is not None
        assert get_user_by_email(db, email) is not None
    finally:
        db.query(User).filter(User.email == email).delete(synchronize_session=False)
        db.commit()
        db.close()
