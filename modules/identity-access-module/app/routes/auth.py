"""M1 - User Access Management Start
Defines login, current-user, and password-change API routes.
M1 End"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import CurrentUser, LoginRequest, PasswordChangeRequest, TokenResponse, User
from app.services.auth_service import authenticate_user, build_login_token, get_current_active_user
from app.services.user_service import change_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(login_request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return a bearer token."""
    user = authenticate_user(db, login_request)
    return TokenResponse(
        access_token=build_login_token(user),
        password_change_required=user.must_change_password,
    )


@router.get("/me", response_model=CurrentUser)
def get_me(current_user: User = Depends(get_current_active_user)) -> CurrentUser:
    """Return the authenticated user's profile."""
    return CurrentUser.model_validate(current_user)


@router.post("/change-password", response_model=CurrentUser)
def change_current_password(
    password_change: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> CurrentUser:
    """Change the authenticated user's password."""
    return CurrentUser.model_validate(change_password(db, current_user, password_change.new_password))


# M1 End
