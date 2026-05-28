"""M1 - User Access Management Start
Verifies PostgreSQL account state after the administrator-created user evidence flow.
M1 End"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "tests/scripts" / "common"))
from test_config import configured_path

MODULE_ROOT = configured_path(__file__, "moduleFolders", "IdentityAccess")
sys.path.insert(0, str(MODULE_ROOT))

from app.db import SessionLocal
from app.models.user import User


ADMIN_EMAIL = "m1.regression.admin.20260523@example.com"
NEW_USER_EMAIL = "m1.regression.user.20260523@example.com"


def main() -> int:
    db = SessionLocal()
    try:
        users = {
            user.email: user
            for user in db.query(User)
            .filter(User.email.in_([ADMIN_EMAIL, NEW_USER_EMAIL]))
            .order_by(User.email)
            .all()
        }
        admin = users.get(ADMIN_EMAIL)
        created_user = users.get(NEW_USER_EMAIL)

        print("M1 ADMIN USER FLOW DATABASE CHECK")
        print("=" * 39)
        print(f"PostgreSQL database contains admin test user: {admin is not None}")
        print(f"Admin role is admin: {getattr(admin, 'role', None) == 'admin'}")
        print(f"Admin password change required: {getattr(admin, 'must_change_password', None)}")
        print(f"PostgreSQL database contains created test user: {created_user is not None}")
        print(f"Created user role is user: {getattr(created_user, 'role', None) == 'user'}")
        print(f"Created user is active: {getattr(created_user, 'is_active', None)}")
        print(f"Created user password change required after reset: {getattr(created_user, 'must_change_password', None)}")

        passed = (
            admin is not None
            and admin.role == "admin"
            and admin.must_change_password is False
            and created_user is not None
            and created_user.role == "user"
            and created_user.is_active is True
            and created_user.must_change_password is False
        )
        print(f"Result: {'PASSED' if passed else 'FAILED'}")
        return 0 if passed else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
