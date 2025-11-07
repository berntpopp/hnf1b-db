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
