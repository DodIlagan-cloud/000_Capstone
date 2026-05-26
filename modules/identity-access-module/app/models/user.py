"""M1 - User Access Management Start
Defines database and API models for authenticated user accounts.
M1 End"""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import Boolean, Column, DateTime, String

from app.models.database import Base


class UserRole:
    """Supported application roles."""

    ADMIN = "admin"
    USER = "user"

    @classmethod
    def values(cls) -> set[str]:
        """Return allowed role values."""
        return {cls.ADMIN, cls.USER}


class User(Base):
    """Database model for application users."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, nullable=False, default=True)
    must_change_password = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login_at = Column(DateTime, nullable=True)


def normalize_email(email: str) -> str:
    """Normalize an email login username."""
    return email.strip().lower()


def validate_email(email: str) -> str:
    """Validate and normalize an email login username."""
    normalized = normalize_email(email)
    if not normalized or len(normalized) > 255:
        raise ValueError("Email must be between 1 and 255 characters")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalized):
        raise ValueError("Email must be a valid email address")
    return normalized


def validate_password(password: str) -> str:
    """Validate password complexity requirements."""
    if not password or not password.strip():
        raise ValueError("Password is required")
    if len(password) < 8 or len(password) > 128:
        raise ValueError("Password must be between 8 and 128 characters")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("Password must include at least one letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must include at least one number")
    return password


def validate_full_name(full_name: Optional[str]) -> Optional[str]:
    """Validate and normalize an optional full name."""
    if full_name is None:
        return None

    normalized = full_name.strip()
    if not normalized:
        return None
    if len(normalized) < 2 or len(normalized) > 100:
        raise ValueError("Full name must be between 2 and 100 characters")
    if not re.match(r"^[A-Za-z .'-]+$", normalized):
        raise ValueError("Full name contains unsupported characters")
    return normalized


def validate_role(role: str) -> str:
    """Validate a user role value."""
    normalized = role.strip().lower()
    if normalized not in UserRole.values():
        raise ValueError("Role must be admin or user")
    return normalized


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_login_email(cls, value: str) -> str:
        """Validate login email."""
        return validate_email(value)


class TokenResponse(BaseModel):
    """Response model for bearer token login."""

    access_token: str
    token_type: str = "bearer"
    password_change_required: bool = False


class PasswordChangeRequest(BaseModel):
    """Request model for authenticated password changes."""

    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        """Validate replacement password."""
        return validate_password(value)


class UserCreate(BaseModel):
    """Request model for administrator-created users."""

    email: str = Field(..., max_length=255)
    full_name: Optional[str] = Field(None, max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role: str = UserRole.USER
    is_active: bool = True

    @field_validator("email")
    @classmethod
    def validate_user_email(cls, value: str) -> str:
        """Validate user email."""
        return validate_email(value)

    @field_validator("password")
    @classmethod
    def validate_user_password(cls, value: str) -> str:
        """Validate user password."""
        return validate_password(value)

    @field_validator("full_name")
    @classmethod
    def validate_user_full_name(cls, value: Optional[str]) -> Optional[str]:
        """Validate user full name."""
        return validate_full_name(value)

    @field_validator("role")
    @classmethod
    def validate_user_role(cls, value: str) -> str:
        """Validate user role."""
        return validate_role(value)


class UserUpdate(BaseModel):
    """Request model for administrator user updates."""

    email: Optional[str] = Field(None, max_length=255)
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: Optional[str]) -> Optional[str]:
        """Validate optional email."""
        return validate_email(value) if value is not None else None

    @field_validator("password")
    @classmethod
    def validate_optional_password(cls, value: Optional[str]) -> Optional[str]:
        """Validate optional password."""
        return validate_password(value) if value is not None else None

    @field_validator("full_name")
    @classmethod
    def validate_optional_full_name(cls, value: Optional[str]) -> Optional[str]:
        """Validate optional full name."""
        return validate_full_name(value)

    @field_validator("role")
    @classmethod
    def validate_optional_role(cls, value: Optional[str]) -> Optional[str]:
        """Validate optional role."""
        return validate_role(value) if value is not None else None


class UserResponse(BaseModel):
    """Response model for user account data."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    must_change_password: bool


class CurrentUser(UserResponse):
    """Response model for the authenticated user."""


# M1 End
