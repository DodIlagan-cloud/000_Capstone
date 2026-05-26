"""M1 - User Access Management Start
Manages Identity Access user persistence, bootstrap, and password setup.
M1 End"""

from fastapi import status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ErrorType, api_error
from app.models.user import User, UserCreate, UserRole, UserUpdate, normalize_email
from app.utils.security import hash_password


def get_user_by_email(db: Session, email: str) -> User | None:
    """Find a user by normalized email."""
    return db.query(User).filter(User.email == normalize_email(email)).first()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    """Find a user by identifier."""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_create: UserCreate) -> User:
    """Create a user account."""
    if get_user_by_email(db, user_create.email):
        raise api_error(ErrorType.USER_ALREADY_EXISTS, "A user with this email already exists")

    user = User(
        email=normalize_email(user_create.email),
        full_name=user_create.full_name,
        hashed_password=hash_password(user_create.password),
        role=user_create.role,
        is_active=user_create.is_active,
        must_change_password=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise api_error(ErrorType.USER_ALREADY_EXISTS, "A user with this email already exists") from exc
    db.refresh(user)
    return user


def create_initial_admin(db: Session, email: str, password: str, full_name: str | None = None) -> User:
    """Create the first administrator when no users exist."""
    if db.query(User).first():
        raise api_error(
            ErrorType.FORBIDDEN,
            "Initial administrator can only be created before other users exist",
            status.HTTP_403_FORBIDDEN,
        )

    admin = create_user(
        db,
        UserCreate(
            email=email,
            full_name=full_name,
            password=password,
            role=UserRole.ADMIN,
        ),
    )
    admin.must_change_password = True
    db.commit()
    db.refresh(admin)
    return admin


def change_password(db: Session, user: User, password: str) -> User:
    """Replace a user password and clear first-login password setup."""
    user.hashed_password = hash_password(password)
    user.must_change_password = False
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    """Return all users ordered by email."""
    return db.query(User).order_by(User.email).all()


def update_user(db: Session, user: User, user_update: UserUpdate) -> User:
    """Update a user account."""
    update_data = user_update.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"] is not None:
        existing_user = get_user_by_email(db, update_data["email"])
        if existing_user and existing_user.id != user.id:
            raise api_error(ErrorType.USER_ALREADY_EXISTS, "A user with this email already exists")
        user.email = normalize_email(update_data["email"])
    if "full_name" in update_data:
        user.full_name = update_data["full_name"]
    if "password" in update_data and update_data["password"] is not None:
        user.hashed_password = hash_password(update_data["password"])
        user.must_change_password = True
    if "role" in update_data and update_data["role"] is not None:
        user.role = update_data["role"]
    if "is_active" in update_data and update_data["is_active"] is not None:
        user.is_active = update_data["is_active"]

    db.commit()
    db.refresh(user)
    return user


def has_other_active_admin(db: Session, user: User) -> bool:
    """Return whether another active administrator exists."""
    return (
        db.query(User)
        .filter(User.id != user.id, User.role == UserRole.ADMIN, User.is_active.is_(True))
        .first()
        is not None
    )


# M1 End
