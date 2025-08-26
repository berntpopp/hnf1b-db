# app/repositories/user.py
"""User repository for handling user-related database operations."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with authentication-specific methods."""

    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            username: The username to search for

        Returns:
            User instance or None if not found
        """
        return await self.get_by_field("user_name", username)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email address.

        Args:
            email: The email address to search for

        Returns:
            User instance or None if not found
        """
        return await self.get_by_field("email", email)

    async def get_by_user_id(self, user_id: int) -> Optional[User]:
        """Get user by user_id (numeric identifier).

        Args:
            user_id: The numeric user ID

        Returns:
            User instance or None if not found
        """
        return await self.get_by_field("user_id", user_id)

    async def authenticate(self, username: str, password: str) -> Optional[User]:
        """Authenticate user by username and password.

        Note: This is a basic implementation. In production, you should use
        proper password hashing (e.g., bcrypt) instead of plain text comparison.

        Args:
            username: The username
            password: The password (should be hashed)

        Returns:
            User instance if authentication successful, None otherwise
        """
        user = await self.get_by_username(username)
        if (
            user and user.password == password
        ):  # Replace with proper password verification
            return user
        return None

    async def create_user(
        self,
        user_id: int,
        user_name: str,
        password: str,  # Should be hashed before calling this method
        email: str,
        user_role: str,
        first_name: str,
        family_name: str,
        orcid: Optional[str] = None,
    ) -> User:
        """Create a new user with validation.

        Args:
            user_id: Numeric user identifier
            user_name: Username
            password: Hashed password
            email: Email address
            user_role: User role
            first_name: First name
            family_name: Family name
            orcid: Optional ORCID identifier

        Returns:
            Created user instance
        """
        return await self.create(
            user_id=user_id,
            user_name=user_name,
            password=password,
            email=email,
            user_role=user_role,
            first_name=first_name,
            family_name=family_name,
            orcid=orcid,
        )

    async def get_reviewers(self) -> list[User]:
        """Get all users with reviewer role.

        Returns:
            List of reviewer users
        """
        query = select(User).where(User.user_role == "reviewer")
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def is_username_available(self, username: str) -> bool:
        """Check if username is available.

        Args:
            username: Username to check

        Returns:
            True if available, False if taken
        """
        return not await self.exists(user_name=username)

    async def is_email_available(self, email: str) -> bool:
        """Check if email is available.

        Args:
            email: Email to check

        Returns:
            True if available, False if taken
        """
        return not await self.exists(email=email)
