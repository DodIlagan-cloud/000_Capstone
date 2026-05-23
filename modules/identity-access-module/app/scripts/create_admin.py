"""M1 - User Access Management Start
Creates the initial administrator user for the standalone Identity Access Module.
M1 End"""

from app.config import settings
from app.db import SessionLocal, init_db
from app.services.user_service import create_initial_admin


def main() -> None:
    """Create the initial administrator account."""
    if not settings.default_admin_email or not settings.default_admin_password:
        raise SystemExit(
            "Set DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD before creating the initial admin."
        )

    init_db()
    db = SessionLocal()
    try:
        admin = create_initial_admin(
            db,
            settings.default_admin_email,
            settings.default_admin_password,
        )
    except Exception as exc:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict) and detail.get("message"):
            raise SystemExit(detail["message"]) from exc
        raise
    finally:
        db.close()

    print(f"Initial administrator created: {admin.email}")


if __name__ == "__main__":
    main()
# M1 End
