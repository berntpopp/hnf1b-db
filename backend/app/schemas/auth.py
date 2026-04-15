"""Pydantic schemas for authentication and user management."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.password import validate_password_strength


class InviteRequest(BaseModel):
    """Admin invite request."""

    email: EmailStr
    role: str = Field("viewer", pattern="^(admin|curator|viewer)$")


class InviteResponse(BaseModel):
    """Invite creation response."""

    email: str
    role: str
    expires_at: datetime
    token: str | None = None  # Dev-only: raw token for testing


class InviteAcceptRequest(BaseModel):
    """Invite accept request — user sets their own credentials."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format (same rules as UserCreate)."""
        v = v.lower()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        if v in ["admin", "root", "system", "administrator"]:
            raise ValueError(f"Username '{v}' is reserved")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        validate_password_strength(v)
        return v


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserLogin(BaseModel):
    """User login credentials."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class UserCreate(BaseModel):
    """User creation request (admin only)."""

    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str | None = Field(None, max_length=255)
    role: str = Field("viewer", pattern="^(admin|curator|viewer)$")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        # Lowercase and check format
        v = v.lower()
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, - and _")
        # Check reserved names
        if v in ["admin", "root", "system", "administrator"]:
            raise ValueError(f"Username '{v}' is reserved")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength."""
        validate_password_strength(v)  # Centralized validation
        return v


class UserUpdateAdmin(BaseModel):
    """User update request — admin-only fields.

    Wave 5b Task 7: renamed from UserUpdate to make BOPLA scope explicit.
    This schema accepts role + is_active — NEVER use it on a user-facing
    update path. Use UserUpdatePublic for /auth/me or similar public paths.
    """

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = Field(None, max_length=255)
    role: str | None = Field(None, pattern="^(admin|curator|viewer)$")
    is_active: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        """Validate password strength if provided."""
        if v is not None:
            validate_password_strength(v)
        return v


class UserUpdatePublic(BaseModel):
    """User update request — user-facing self-service fields only.

    Wave 5b Task 7 (BOPLA): any public update endpoint (e.g., a future
    /auth/me PATCH for profile self-editing) MUST accept UserUpdatePublic
    and NEVER UserUpdateAdmin. Structurally excludes role, is_active,
    is_superuser, is_verified, is_fixture_user, hashed_password,
    refresh_token, failed_login_attempts, locked_until, permissions.

    This schema is NOT YET USED by any endpoint in Wave 5b. It exists so
    that Wave 5c (identity lifecycle) and any future profile-editing UI
    can consume it without having to carve a subset out of UserUpdateAdmin
    or (worse) reuse UserUpdateAdmin and hope nobody notices.
    """

    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8)
    full_name: str | None = Field(None, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str | None) -> str | None:
        """Validate password strength if provided."""
        if v is not None:
            validate_password_strength(v)
        return v


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength."""
        validate_password_strength(v)
        return v


class PasswordResetRequest(BaseModel):
    """Password reset request — email only."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation — new password."""

    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate password strength."""
        validate_password_strength(v)
        return v


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    token: str | None = None  # Dev-only: raw token for testing


class UserResponse(BaseModel):
    """User response (passwords never included)."""

    id: int
    username: str
    email: str
    full_name: str | None
    role: str
    permissions: list[str]
    is_active: bool
    is_verified: bool
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    """Role definition response."""

    role: str
    description: str
    permissions: list[str]
