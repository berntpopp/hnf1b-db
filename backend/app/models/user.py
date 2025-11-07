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
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
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
            List of permission strings
            (e.g., ["phenopackets:read", "phenopackets:write"])
        """
        from app.auth.permissions import get_role_permissions

        return get_role_permissions(self.role)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"<User(id={self.id}, username={self.username!r}, role={self.role!r})>"
