"""M1 - User Access Management Start
Authenticates users and exposes reusable authorization dependencies.
M1 End"""

from datetime import datetime, timezone

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.errors import ErrorType, api_error
from app.models.user import LoginRequest, User, UserRole
from app.services.user_service import get_user_by_email, get_user_by_id
from app.utils.security import create_access_token, decode_access_token, verify_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")


def authenticate_user(db: Session, login_request: LoginRequest) -> User:
    """Authenticate active user credentials."""
    user = get_user_by_email(db, login_request.email)
    if not user or not verify_password(login_request.password, user.hashed_password):
        raise api_error(
            ErrorType.INVALID_CREDENTIALS,
            "Invalid email or password",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        raise api_error(ErrorType.INACTIVE_USER, "User account is inactive", status.HTTP_403_FORBIDDEN)

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    return user


def build_login_token(user: User) -> str:
    """Build a bearer token for an authenticated user."""
    return create_access_token(subject=user.id)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Return the authenticated user for a bearer token."""
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise api_error(ErrorType.INVALID_TOKEN, "Invalid or expired token", status.HTTP_401_UNAUTHORIZED)

    user = get_user_by_id(db, str(payload["sub"]))
    if not user:
        raise api_error(ErrorType.UNAUTHENTICATED, "Authenticated user was not found", status.HTTP_401_UNAUTHORIZED)
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the authenticated user when the account is active."""
    if not current_user.is_active:
        raise api_error(ErrorType.INACTIVE_USER, "User account is inactive", status.HTTP_403_FORBIDDEN)
    return current_user


def require_password_ready(current_user: User = Depends(get_current_active_user)) -> User:
    """Require first-login password setup before ordinary protected actions."""
    if current_user.must_change_password:
        raise api_error(
            ErrorType.FORBIDDEN,
            "Password change is required before continuing",
            status.HTTP_403_FORBIDDEN,
        )
    return current_user


def require_admin(current_user: User = Depends(require_password_ready)) -> User:
    """Require an authenticated administrator."""
    if current_user.role != UserRole.ADMIN:
        raise api_error(ErrorType.FORBIDDEN, "Administrator access is required", status.HTTP_403_FORBIDDEN)
    return current_user


# M1 End
