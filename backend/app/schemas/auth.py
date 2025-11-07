"""Pydantic schemas for authentication and user management."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth.password import validate_password_strength


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


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


class UserUpdate(BaseModel):
    """User update request (admin only)."""

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
