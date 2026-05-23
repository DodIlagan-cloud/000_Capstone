"""M1 - User Access Management Start
Prepares PostgreSQL test-only users for the administrator-created user evidence flow.
M1 End"""

from __future__ import annotations

import sys
from pathlib import Path


MODULE_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(MODULE_ROOT))

from app.db import SessionLocal, init_db
from app.models.user import User, UserRole, normalize_email
from app.utils.security import hash_password


ADMIN_EMAIL = "m1.regression.admin.20260523@example.com"
ADMIN_PASSWORD = "AdminTest123"
NEW_USER_EMAIL = "m1.regression.user.20260523@example.com"


def main() -> int:
    init_db()
    db = SessionLocal()
    try:
        emails = [normalize_email(ADMIN_EMAIL), normalize_email(NEW_USER_EMAIL)]
        db.query(User).filter(User.email.in_(emails)).delete(synchronize_session=False)
        db.commit()

        admin = User(
            email=normalize_email(ADMIN_EMAIL),
            full_name="M1 Regression Admin",
            hashed_password=hash_password(ADMIN_PASSWORD),
            role=UserRole.ADMIN,
            is_active=True,
            must_change_password=False,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("M1 PostgreSQL test setup")
        print(f"Admin test user: {admin.email}")
        print(f"New user reserved for browser creation: {NEW_USER_EMAIL}")
        print("Result: PASSED")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
