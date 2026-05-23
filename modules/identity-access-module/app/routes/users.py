"""M1 - User Access Management Start
Defines administrator user-management API routes.
M1 End"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import ErrorType, api_error
from app.models.user import User, UserCreate, UserResponse, UserRole, UserUpdate
from app.services.auth_service import require_admin, require_password_ready
from app.services.user_service import (
    create_user,
    get_user_by_id,
    has_other_active_admin,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_account(
    user_create: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserResponse:
    """Create a user account."""
    return UserResponse.model_validate(create_user(db, user_create))


@router.get("", response_model=list[UserResponse])
def list_user_accounts(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[UserResponse]:
    """List user accounts."""
    return [UserResponse.model_validate(user) for user in list_users(db)]


@router.get("/{user_id}", response_model=UserResponse)
def get_user_account(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_password_ready),
) -> UserResponse:
    """Return a user account."""
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise api_error(ErrorType.FORBIDDEN, "Users can only access their own profile", status.HTTP_403_FORBIDDEN)

    user = get_user_by_id(db, user_id)
    if not user:
        raise api_error(ErrorType.USER_NOT_FOUND, "User was not found", status.HTTP_404_NOT_FOUND)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user_account(
    user_id: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
) -> UserResponse:
    """Update a user account."""
    user = get_user_by_id(db, user_id)
    if not user:
        raise api_error(ErrorType.USER_NOT_FOUND, "User was not found", status.HTTP_404_NOT_FOUND)

    update_data = user_update.model_dump(exclude_unset=True)
    demotes_admin = update_data.get("role") and update_data["role"] != UserRole.ADMIN
    deactivates_user = update_data.get("is_active") is False
    if user.role == UserRole.ADMIN and (demotes_admin or deactivates_user) and not has_other_active_admin(db, user):
        raise api_error(ErrorType.FORBIDDEN, "At least one active administrator is required", status.HTTP_403_FORBIDDEN)

    return UserResponse.model_validate(update_user(db, user, user_update))


# M1 End
