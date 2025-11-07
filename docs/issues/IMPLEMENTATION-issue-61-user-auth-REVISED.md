# Issue #61: User Authentication & Management - REVISED IMPLEMENTATION PLAN

**Status:** Ready for Implementation
**Estimated Time:** 13 hours
**Complexity:** Medium
**Review Status:** ✅ Addresses all review findings

---

## Executive Summary

Implement production-ready JWT authentication with role-based access control (RBAC) for HNF1B-DB. This **revised plan** consolidates two previous plans, fixes architectural issues, removes code duplication, and aligns with existing codebase patterns.

**Key Changes from Original:**
- ✅ Uses async SQLAlchemy ORM exclusively (no raw SQL)
- ✅ Removes all code duplication (DRY)
- ✅ Follows existing codebase patterns
- ✅ Simplified architecture (~830 lines vs 2,400)
- ✅ Complete test infrastructure
- ✅ Modern Python practices (Pydantic v2, timezone-aware datetime)
- ✅ Reduced time: 13h vs 20h

---

## Prerequisites & Cleanup

### 1. Verify Dependencies

```bash
# Backend dependencies (already installed)
cd backend
uv pip list | grep -E "passlib|bcrypt|pyjwt|sqlalchemy"
# Should show:
#   passlib[bcrypt]>=1.7.4
#   bcrypt>=3.2.0,<5.0.0
#   pyjwt>=2.10.1
#   sqlalchemy[asyncio]>=2.0.25

# Frontend dependencies
cd ../frontend
npm list pinia
# Should show: pinia@2.3.1

# If Pinia missing:
npm install pinia@^2.3.1
```

### 2. Create Directory Structure

```bash
cd backend/app

# Create new directories
mkdir -p models
mkdir -p auth
mkdir -p repositories

# Verify structure
tree -L 2 app/
# app/
# ├── models/         # NEW
# ├── auth/           # NEW
# ├── repositories/   # NEW
# ├── api/
# ├── phenopackets/
# └── ...
```

### 3. Archive Old Files

```bash
# Move existing auth files to archive (don't delete yet)
mkdir -p ../archive
mv app/auth.py ../archive/auth.py.old
mv app/auth_endpoints.py ../archive/auth_endpoints.py.old

# Keep copies for reference during migration
```

---

## Phase 1: Core Models & Password Utilities (3 hours)

### File 1: `backend/app/models/__init__.py`

**Action:** CREATE new file

```python
"""SQLAlchemy models for HNF1B-DB."""

from app.models.user import User

__all__ = ["User"]
```

### File 2: `backend/app/models/user.py`

**Action:** CREATE new file (150 lines)

```python
"""User model with authentication and role management."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    pass  # For future relationship imports


class User(Base):
    """User model with authentication, RBAC, and account security.

    Attributes:
        id: Primary key
        email: Unique email address (indexed)
        username: Unique username (indexed)
        hashed_password: Bcrypt hashed password
        full_name: Optional full name
        role: User role (admin/curator/viewer), indexed
        is_active: Account active status, indexed
        is_verified: Email verification status
        last_login: Last successful login timestamp
        failed_login_attempts: Failed login counter for lockout
        locked_until: Account lock expiration timestamp
        refresh_token: Current refresh token (rotated on use)
        created_at: Account creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "users"

    # Primary Key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Authentication Fields
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    username: Mapped[str] = mapped_column(
        String(50), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Role & Status (indexed for fast filtering)
    role: Mapped[str] = mapped_column(
        String(20), default="viewer", nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Security Fields
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Token Management
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == "admin"

    @property
    def is_curator(self) -> bool:
        """Check if user has curator or admin role."""
        return self.role in ["admin", "curator"]

    def get_permissions(self) -> list[str]:
        """Get permissions based on role.

        Returns:
            List of permission strings (e.g., ["phenopackets:read", "phenopackets:write"])
        """
        from app.auth.permissions import get_role_permissions

        return get_role_permissions(self.role)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, username={self.username!r}, role={self.role!r})>"
```

### File 3: `backend/app/auth/__init__.py`

**Action:** CREATE new file

```python
"""Authentication and authorization module."""

from app.auth.dependencies import get_current_user, require_admin, require_curator
from app.auth.password import get_password_hash, validate_password_strength, verify_password
from app.auth.permissions import Role, get_role_permissions
from app.auth.tokens import create_access_token, create_refresh_token, verify_token

__all__ = [
    # Dependencies
    "get_current_user",
    "require_admin",
    "require_curator",
    # Password
    "get_password_hash",
    "validate_password_strength",
    "verify_password",
    # Permissions
    "Role",
    "get_role_permissions",
    # Tokens
    "create_access_token",
    "create_refresh_token",
    "verify_token",
]
```

### File 4: `backend/app/auth/permissions.py`

**Action:** CREATE new file (60 lines)

```python
"""Role and permission definitions - Single source of truth."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """User roles enum."""

    ADMIN = "admin"
    CURATOR = "curator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class RoleDefinition:
    """Role definition with description and permissions."""

    name: str
    description: str
    permissions: tuple[str, ...]  # Immutable


# Single source of truth for role permissions
ROLE_DEFINITIONS: dict[Role, RoleDefinition] = {
    Role.ADMIN: RoleDefinition(
        name="admin",
        description="Administrator with full system access",
        permissions=(
            "users:read",
            "users:write",
            "users:delete",
            "phenopackets:read",
            "phenopackets:write",
            "phenopackets:delete",
            "variants:read",
            "variants:write",
            "variants:delete",
            "ingestion:run",
            "system:manage",
            "logs:read",
        ),
    ),
    Role.CURATOR: RoleDefinition(
        name="curator",
        description="Data curator with editing permissions",
        permissions=(
            "phenopackets:read",
            "phenopackets:write",
            "variants:read",
            "variants:write",
            "ingestion:run",
        ),
    ),
    Role.VIEWER: RoleDefinition(
        name="viewer",
        description="Public read-only access (default)",
        permissions=("phenopackets:read", "variants:read", "publications:read"),
    ),
}


def get_role_permissions(role: str) -> list[str]:
    """Get permissions for a role.

    Args:
        role: Role name string

    Returns:
        List of permission strings

    Raises:
        KeyError: If role is invalid
    """
    return list(ROLE_DEFINITIONS[Role(role)].permissions)


def get_all_roles() -> list[dict[str, str | list[str]]]:
    """Get all role definitions for API responses.

    Returns:
        List of role definitions with name, description, permissions
    """
    return [
        {
            "role": definition.name,
            "description": definition.description,
            "permissions": list(definition.permissions),
        }
        for definition in ROLE_DEFINITIONS.values()
    ]
```

### File 5: `backend/app/auth/password.py`

**Action:** CREATE new file (50 lines)

```python
"""Password hashing and validation utilities."""

from passlib.context import CryptContext

from app.config import settings

# Bcrypt password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hash

    Returns:
        True if password matches hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.

    Args:
        password: Password to validate

    Raises:
        ValueError: If password doesn't meet requirements with detailed message
    """
    errors = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Must be at least {settings.PASSWORD_MIN_LENGTH} characters")

    if not any(c.isupper() for c in password):
        errors.append("Must contain uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Must contain lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Must contain digit")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Must contain special character")

    if errors:
        raise ValueError(f"Password validation failed: {'; '.join(errors)}")
```

### File 6: `backend/app/auth/tokens.py`

**Action:** CREATE new file (80 lines)

```python
"""JWT token creation and verification."""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from app.config import settings


def create_access_token(subject: str, role: str, permissions: list[str]) -> str:
    """Create JWT access token.

    Args:
        subject: Username (JWT sub claim)
        role: User role
        permissions: List of permission strings

    Returns:
        Encoded JWT token string
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": subject,
        "type": "access",
        "role": role,
        "permissions": permissions,
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create JWT refresh token.

    Args:
        subject: Username (JWT sub claim)

    Returns:
        Encoded JWT refresh token string
    """
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "sub": subject,
        "type": "refresh",
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify and decode JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload

    Raises:
        HTTPException: 401 if token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )

        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type, expected {token_type}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
```

### File 7: `backend/app/config.py`

**Action:** MODIFY existing file - Add authentication settings

**Find this section (around line 20):**
```python
    # Authentication
    JWT_SECRET: str = Field(default="")  # Required, will be loaded from environment
```

**Replace with:**
```python
    # Authentication - JWT
    JWT_SECRET: str = Field(default="")  # Required, will be loaded from environment
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Authentication - Password Security
    PASSWORD_MIN_LENGTH: int = 8
    MAX_LOGIN_ATTEMPTS: int = 5
    ACCOUNT_LOCKOUT_MINUTES: int = 15

    # Default Admin Credentials (for initial setup)
    ADMIN_USERNAME: str = "admin"
    ADMIN_EMAIL: str = "admin@hnf1b-db.local"
    ADMIN_PASSWORD: str = "ChangeMe!Admin2025"
```

---

## Phase 2: Database Migration & Auth Dependencies (2 hours)

### File 8: `backend/alembic/versions/005_create_users_table.py`

**Action:** CREATE new Alembic migration

```bash
# Generate migration file
cd backend
uv run alembic revision -m "create_users_table"
# Note the generated filename (e.g., abc123_create_users_table.py)
```

**Edit the generated file:**

```python
"""Create users table for authentication.

Revision ID: <generated>
Revises: 004_merge_heads
Create Date: <generated>
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "<generated_id>"
down_revision = "004_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users table with all authentication fields."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )

    # Create indexes for fast lookups
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_index(op.f("ix_users_role"), "users", ["role"], unique=False)
    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)


def downgrade() -> None:
    """Drop users table and indexes."""
    op.drop_index(op.f("ix_users_is_active"), table_name="users")
    op.drop_index(op.f("ix_users_role"), table_name="users")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")
```

### File 9: `backend/app/auth/dependencies.py`

**Action:** CREATE new file (80 lines)

```python
"""FastAPI dependencies for authentication and authorization."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import verify_token
from app.database import get_db
from app.models.user import User

# FastAPI security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        User model instance

    Raises:
        HTTPException: 401 if token invalid, user not found, or account locked
        HTTPException: 423 if account is locked
    """
    # Verify and decode token
    token = credentials.credentials
    payload = verify_token(token, token_type="access")

    # Extract username from token
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Fetch user from database
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}",
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role for endpoint access.

    Args:
        current_user: Authenticated user

    Returns:
        User instance if admin

    Raises:
        HTTPException: 403 if not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_curator(current_user: User = Depends(get_current_user)) -> User:
    """Require curator or admin role for endpoint access.

    Args:
        current_user: Authenticated user

    Returns:
        User instance if curator or admin

    Raises:
        HTTPException: 403 if not curator/admin
    """
    if not current_user.is_curator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Curator or admin access required",
        )
    return current_user
```

---

## Phase 3: Pydantic Schemas & Repository (2 hours)

### File 10: `backend/app/schemas/auth.py`

**Action:** CREATE new file (120 lines)

```python
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
```

### File 11: `backend/app/repositories/user_repository.py`

**Action:** CREATE new file (150 lines)

```python
"""User repository for database operations."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.config import settings
from app.models.user import User
from app.schemas.auth import UserCreate, UserUpdate


class UserRepository:
    """Repository for user CRUD operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session.

        Args:
            db: Async SQLAlchemy session
        """
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        """Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User instance or None if not found
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username.

        Args:
            username: Username

        Returns:
            User instance or None if not found
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get user by email.

        Args:
            email: Email address

        Returns:
            User instance or None if not found
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create(self, user_data: UserCreate) -> User:
        """Create new user.

        Args:
            user_data: User creation data

        Returns:
            Created user instance
        """
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            role=user_data.role,
            is_active=True,
            is_verified=False,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User, user_data: UserUpdate) -> User:
        """Update user fields.

        Args:
            user: User instance to update
            user_data: Update data

        Returns:
            Updated user instance
        """
        # Update only provided fields
        if user_data.email is not None:
            user.email = user_data.email

        if user_data.password is not None:
            user.hashed_password = get_password_hash(user_data.password)

        if user_data.full_name is not None:
            user.full_name = user_data.full_name

        if user_data.role is not None:
            user.role = user_data.role

        if user_data.is_active is not None:
            user.is_active = user_data.is_active

        user.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        """Delete user.

        Args:
            user: User instance to delete
        """
        await self.db.delete(user)
        await self.db.commit()

    async def list_users(
        self, skip: int = 0, limit: int = 100, role: str | None = None
    ) -> list[User]:
        """List users with pagination and optional filtering.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            role: Optional role filter

        Returns:
            List of user instances
        """
        query = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())

        if role:
            query = query.where(User.role == role)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def record_failed_login(self, user: User) -> None:
        """Record failed login attempt and lock account if needed.

        Args:
            user: User instance
        """
        user.failed_login_attempts += 1

        # Lock account after max attempts
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_MINUTES
            )

        await self.db.commit()

    async def record_successful_login(self, user: User) -> None:
        """Record successful login and reset failed attempts.

        Args:
            user: User instance
        """
        user.last_login = datetime.now(timezone.utc)
        user.failed_login_attempts = 0
        user.locked_until = None
        await self.db.commit()

    async def update_refresh_token(self, user: User, refresh_token: str) -> None:
        """Store refresh token for user.

        Args:
            user: User instance
            refresh_token: Refresh token to store
        """
        user.refresh_token = refresh_token
        await self.db.commit()
```

---

## Phase 4: Authentication Endpoints (3 hours)

### File 12: `backend/app/api/auth_endpoints.py`

**Action:** CREATE new file (replacing old one) - 250 lines

```python
"""Authentication API endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_admin,
    verify_password,
    verify_token,
)
from app.auth.permissions import get_all_roles
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    PasswordChange,
    RefreshTokenRequest,
    RoleResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.utils.audit_logger import log_user_action

router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Login with username and password.

    Returns JWT access token and refresh token.

    **Security:**
    - Password verified with bcrypt
    - Account lockout after 5 failed attempts (15 min)
    - Tokens signed with JWT_SECRET

    **Returns:**
    - 200: Login successful with tokens
    - 401: Invalid credentials
    - 423: Account locked
    """
    repo = UserRepository(db)

    # Get user
    user = await repo.get_by_username(credentials.username)

    # Verify password
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Record failed attempt if user exists
        if user:
            await repo.record_failed_login(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Create tokens
    access_token = create_access_token(
        user.username, user.role, user.get_permissions()
    )
    refresh_token = create_refresh_token(user.username)

    # Update user record
    await repo.record_successful_login(user)
    await repo.update_refresh_token(user, refresh_token)

    # Log successful login
    await log_user_action(
        db=db,
        user_id=user.id,
        action="LOGIN",
        details=f"User '{user.username}' logged in",
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_access_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Refresh access token using refresh token.

    Implements token rotation for security.

    **Returns:**
    - 200: New access token and refresh token
    - 401: Invalid or expired refresh token
    """
    # Verify refresh token
    payload = verify_token(request.refresh_token, token_type="refresh")

    # Get user
    repo = UserRepository(db)
    user = await repo.get_by_username(payload["sub"])

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Verify stored refresh token matches (token rotation)
    if user.refresh_token != request.refresh_token:
        # Possible token theft - invalidate all tokens
        await repo.update_refresh_token(user, "")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Create new tokens (rotation)
    new_access_token = create_access_token(
        user.username, user.role, user.get_permissions()
    )
    new_refresh_token = create_refresh_token(user.username)

    # Store new refresh token
    await repo.update_refresh_token(user, new_refresh_token)

    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current authenticated user information.

    **Returns:**
    - 200: User information
    - 401: Not authenticated
    """
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        permissions=current_user.get_permissions(),
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Logout by invalidating refresh token.

    **Returns:**
    - 200: Logout successful
    """
    repo = UserRepository(db)
    await repo.update_refresh_token(current_user, "")

    await log_user_action(
        db=db,
        user_id=current_user.id,
        action="LOGOUT",
        details=f"User '{current_user.username}' logged out",
    )

    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Change current user's password.

    **Returns:**
    - 200: Password changed successfully
    - 401: Current password incorrect
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    repo = UserRepository(db)
    await repo.update(
        current_user,
        UserUpdate(password=password_data.new_password),
    )

    await log_user_action(
        db=db,
        user_id=current_user.id,
        action="PASSWORD_CHANGE",
        details=f"User '{current_user.username}' changed password",
    )

    return {"message": "Password changed successfully"}


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
) -> list[dict[str, str | list[str]]]:
    """List all available roles and their permissions.

    **Returns:**
    - 200: List of role definitions
    """
    return get_all_roles()


# Admin-only endpoints below this line

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create new user (admin only).

    **Security:**
    - Admin access required
    - Password hashed with bcrypt
    - Validates username/email uniqueness

    **Returns:**
    - 201: User created successfully
    - 403: Not admin
    - 409: Username or email already exists
    """
    repo = UserRepository(db)

    # Check uniqueness
    if await repo.get_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{user_data.username}' already exists",
        )

    if await repo.get_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{user_data.email}' already exists",
        )

    # Create user
    user = await repo.create(user_data)

    await log_user_action(
        db=db,
        user_id=user.id,
        action="USER_CREATED",
        details=f"Admin '{current_user.username}' created user '{user.username}' with role '{user.role}'",
    )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=user.get_permissions(),
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = None,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserResponse]:
    """List all users with pagination (admin only).

    **Returns:**
    - 200: List of users
    - 403: Not admin
    """
    repo = UserRepository(db)
    users = await repo.list_users(skip=skip, limit=limit, role=role)

    return [
        UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            permissions=user.get_permissions(),
            is_active=user.is_active,
            is_verified=user.is_verified,
            last_login=user.last_login,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        for user in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get user by ID (admin only).

    **Returns:**
    - 200: User information
    - 403: Not admin
    - 404: User not found
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        permissions=user.get_permissions(),
        is_active=user.is_active,
        is_verified=user.is_verified,
        last_login=user.last_login,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user (admin only).

    **Returns:**
    - 200: User updated successfully
    - 403: Not admin
    - 404: User not found
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    # Update user
    updated_user = await repo.update(user, user_data)

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_UPDATED",
        details=f"Admin '{current_user.username}' updated user '{user.username}'",
    )

    return UserResponse(
        id=updated_user.id,
        username=updated_user.username,
        email=updated_user.email,
        full_name=updated_user.full_name,
        role=updated_user.role,
        permissions=updated_user.get_permissions(),
        is_active=updated_user.is_active,
        is_verified=updated_user.is_verified,
        last_login=updated_user.last_login,
        created_at=updated_user.created_at,
        updated_at=updated_user.updated_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete user (admin only).

    **Security:**
    - Cannot delete own account (prevents lockout)

    **Returns:**
    - 204: User deleted successfully
    - 403: Not admin
    - 404: User not found
    - 400: Cannot delete own account
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found",
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_DELETED",
        details=f"Admin '{current_user.username}' deleted user '{user.username}'",
    )

    await repo.delete(user)
```

### File 13: `backend/app/main.py`

**Action:** MODIFY - Update router import

**Find line ~50:**
```python
app.include_router(auth_endpoints.router)
```

**Replace with:**
```python
from app.api import auth_endpoints

app.include_router(auth_endpoints.router)
```

### File 14: `backend/app/utils/audit_logger.py`

**Action:** MODIFY - Add user action logging function

**Add to end of file:**

```python
async def log_user_action(
    db: AsyncSession,
    user_id: int,
    action: str,
    details: str,
) -> None:
    """Log user management action.

    Args:
        db: Database session
        user_id: User ID
        action: Action type (LOGIN, LOGOUT, PASSWORD_CHANGE, etc.)
        details: Action details
    """
    # For now, just log to console
    # Future: Store in audit_log table
    logger.info(f"User action: user_id={user_id}, action={action}, details={details}")
```

---

## Phase 5: Admin User Script & Testing (3 hours)

### File 15: `backend/scripts/create_admin_user.py`

**Action:** CREATE new file (100 lines)

```python
"""Create initial admin user for the application."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.password import get_password_hash
from app.config import settings
from app.models.user import User


async def create_admin_user() -> None:
    """Create or update admin user from environment settings."""
    admin_username = settings.ADMIN_USERNAME
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD

    print(f"Creating/updating admin user: {admin_username}")

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_maker() as db:
        try:
            # Check if admin exists
            result = await db.execute(
                select(User).where(
                    (User.username == admin_username) | (User.email == admin_email)
                )
            )
            existing_admin = result.scalar_one_or_none()

            if existing_admin:
                print(f"Admin user exists (ID: {existing_admin.id}), updating...")
                existing_admin.hashed_password = get_password_hash(admin_password)
                existing_admin.role = "admin"
                existing_admin.is_active = True
                existing_admin.is_verified = True
                existing_admin.failed_login_attempts = 0
                existing_admin.locked_until = None
                await db.commit()
                print(f"✅ Admin user updated: {admin_username}")
            else:
                print("Creating new admin user...")
                admin_user = User(
                    email=admin_email,
                    username=admin_username,
                    hashed_password=get_password_hash(admin_password),
                    full_name="Administrator",
                    role="admin",
                    is_active=True,
                    is_verified=True,
                )
                db.add(admin_user)
                await db.commit()
                await db.refresh(admin_user)
                print(f"✅ Admin user created: {admin_username} (ID: {admin_user.id})")

            print(f"\n🔐 Login credentials:")
            print(f"   Username: {admin_username}")
            print(f"   Password: {admin_password}")
            print(
                "\n⚠️  SECURITY: Change the admin password immediately after first login!\n"
            )

        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
            await db.rollback()
            sys.exit(1)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin_user())
```

### File 16: `backend/tests/conftest.py`

**Action:** MODIFY - Add authentication test fixtures

**Add to end of file:**

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.api.auth_endpoints import router as auth_router
from app.auth.password import get_password_hash
from app.main import app
from app.models.user import User


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create test user for authentication tests."""
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("TestPass123!"),
        role="viewer",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    # Cleanup
    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def admin_user(db_session):
    """Create admin user for permission tests."""
    user = User(
        username="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        role="admin",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    yield user

    await db_session.execute(delete(User).where(User.id == user.id))
    await db_session.commit()


@pytest_asyncio.fixture
async def async_client(db_session):
    """Async HTTP client for API testing."""
    from app.database import get_db

    # Override get_db to use test session
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(test_user, async_client):
    """Get auth headers for authenticated requests."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "username": test_user.username,
            "password": "TestPass123!",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def admin_headers(admin_user, async_client):
    """Get auth headers for admin requests."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={
            "username": admin_user.username,
            "password": "AdminPass123!",
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

### File 17: `backend/tests/test_auth.py`

**Action:** CREATE new file (200 lines)

```python
"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient, test_user):
    """Test successful login."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 1800  # 30 minutes


@pytest.mark.asyncio
async def test_login_invalid_credentials(async_client: AsyncClient, test_user):
    """Test login with invalid credentials."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "WrongPassword"},
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client: AsyncClient):
    """Test login with nonexistent user."""
    response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": "nonexistent", "password": "password"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(async_client: AsyncClient, auth_headers):
    """Test getting current user info."""
    response = await async_client.get("/api/v2/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["role"] == "viewer"
    assert "phenopackets:read" in data["permissions"]


@pytest.mark.asyncio
async def test_get_current_user_no_token(async_client: AsyncClient):
    """Test accessing protected endpoint without token."""
    response = await async_client.get("/api/v2/auth/me")

    assert response.status_code == 403  # No token provided


@pytest.mark.asyncio
async def test_token_refresh(async_client: AsyncClient, test_user):
    """Test token refresh."""
    # Login first
    login_response = await async_client.post(
        "/api/v2/auth/login",
        json={"username": test_user.username, "password": "TestPass123!"},
    )
    refresh_token = login_response.json()["refresh_token"]

    # Refresh token
    response = await async_client.post(
        "/api/v2/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Should get new refresh token (rotation)
    assert data["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_logout(async_client: AsyncClient, auth_headers):
    """Test logout."""
    response = await async_client.post("/api/v2/auth/logout", headers=auth_headers)

    assert response.status_code == 200
    assert "Successfully logged out" in response.json()["message"]


@pytest.mark.asyncio
async def test_change_password(async_client: AsyncClient, auth_headers):
    """Test password change."""
    response = await async_client.post(
        "/api/v2/auth/change-password",
        headers=auth_headers,
        json={
            "current_password": "TestPass123!",
            "new_password": "NewPass456!",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_roles(async_client: AsyncClient, auth_headers):
    """Test listing roles."""
    response = await async_client.get("/api/v2/auth/roles", headers=auth_headers)

    assert response.status_code == 200
    roles = response.json()
    assert len(roles) == 3
    role_names = [r["role"] for r in roles]
    assert "admin" in role_names
    assert "curator" in role_names
    assert "viewer" in role_names


# Admin-only endpoint tests

@pytest.mark.asyncio
async def test_create_user_admin(async_client: AsyncClient, admin_headers):
    """Test creating user as admin."""
    response = await async_client.post(
        "/api/v2/auth/users",
        headers=admin_headers,
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "role": "curator",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "curator"


@pytest.mark.asyncio
async def test_create_user_non_admin(async_client: AsyncClient, auth_headers):
    """Test creating user as non-admin (should fail)."""
    response = await async_client.post(
        "/api/v2/auth/users",
        headers=auth_headers,
        json={
            "username": "newuser",
            "email": "new@example.com",
            "password": "NewPass123!",
            "role": "curator",
        },
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_users_admin(async_client: AsyncClient, admin_headers):
    """Test listing users as admin."""
    response = await async_client.get("/api/v2/auth/users", headers=admin_headers)

    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)
    assert len(users) >= 1  # At least admin user


@pytest.mark.asyncio
async def test_delete_user_self(async_client: AsyncClient, admin_headers, admin_user):
    """Test deleting own account (should fail)."""
    response = await async_client.delete(
        f"/api/v2/auth/users/{admin_user.id}",
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert "Cannot delete your own account" in response.json()["detail"]
```

---

## Deployment & Verification

### Step 1: Run Migration

```bash
cd backend

# Run migration
uv run alembic upgrade head

# Verify table created
psql $DATABASE_URL -c "\d users"
```

### Step 2: Create Admin User

```bash
# Set admin credentials in .env (if not already set)
echo "ADMIN_USERNAME=admin" >> .env
echo "ADMIN_EMAIL=admin@hnf1b-db.local" >> .env
echo "ADMIN_PASSWORD=ChangeMe!Admin2025" >> .env

# Create admin user
uv run python scripts/create_admin_user.py

# Expected output:
# ✅ Admin user created: admin (ID: 1)
# 🔐 Login credentials:
#    Username: admin
#    Password: ChangeMe!Admin2025
```

### Step 3: Run Tests

```bash
# Run all tests
make test

# Run only auth tests
uv run pytest backend/tests/test_auth.py -v

# Run with coverage
uv run pytest --cov=app.auth --cov=app.models.user --cov=app.api.auth_endpoints

# Expected: All tests pass, >80% coverage
```

### Step 4: Manual Testing

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeMe!Admin2025"}'

# Save token
TOKEN="<access_token_from_response>"

# 2. Get current user
curl http://localhost:8000/api/v2/auth/me \
  -H "Authorization: Bearer $TOKEN"

# 3. List roles
curl http://localhost:8000/api/v2/auth/roles \
  -H "Authorization: Bearer $TOKEN"

# 4. Create user (admin only)
curl -X POST http://localhost:8000/api/v2/auth/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "curator1",
    "email": "curator@example.com",
    "password": "CuratorPass123!",
    "role": "curator"
  }'

# 5. List users (admin only)
curl http://localhost:8000/api/v2/auth/users \
  -H "Authorization: Bearer $TOKEN"
```

### Step 5: Code Quality Checks

```bash
# Run all checks
make check

# Or individually:
make lint        # Ruff linting
make typecheck   # Mypy type checking
make test        # Pytest

# Expected: All pass with no errors
```

---

## Summary

### Files Created (11 files)
1. `backend/app/models/__init__.py`
2. `backend/app/models/user.py`
3. `backend/app/auth/__init__.py`
4. `backend/app/auth/permissions.py`
5. `backend/app/auth/password.py`
6. `backend/app/auth/tokens.py`
7. `backend/app/auth/dependencies.py`
8. `backend/app/schemas/auth.py`
9. `backend/app/repositories/user_repository.py`
10. `backend/app/api/auth_endpoints.py`
11. `backend/alembic/versions/005_create_users_table.py`
12. `backend/scripts/create_admin_user.py`
13. `backend/tests/test_auth.py`

### Files Modified (3 files)
1. `backend/app/config.py` (+15 lines)
2. `backend/app/main.py` (+2 lines)
3. `backend/app/utils/audit_logger.py` (+10 lines)
4. `backend/tests/conftest.py` (+80 lines)

### Total Lines: ~1,350 lines
- Models: 150
- Auth module: 270 (permissions + password + tokens + dependencies)
- Schemas: 120
- Repository: 150
- Endpoints: 250
- Migration: 60
- Scripts: 100
- Tests: 200
- Config/Utils: 50

### Complexity Reduction
- ✅ From 2,400 lines → 1,350 lines (44% reduction)
- ✅ From 20 hours → 13 hours (35% reduction)
- ✅ Single implementation (no duplication)
- ✅ Follows existing patterns
- ✅ Modern best practices

---

## Next Phase: Frontend Integration (Not in this document)

Frontend implementation will be a separate phase following this backend completion. Key components:
- Pinia auth store
- API client token refresh interceptor
- Router guards
- Login/User Profile/Admin Management views

**Estimated:** 4 additional hours

---

**Implementation Ready:** ✅
**Review Status:** Addresses all findings from REVIEW document
**Estimated Total:** 13 hours backend + 4 hours frontend = **17 hours**
