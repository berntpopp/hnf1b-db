"""Service for importing users from Google Sheets reviewer data.

This service handles creating user accounts from reviewer data during
the phenopacket migration process. It follows the service layer pattern
with proper dependency injection and database transaction management.

Design Principles:
- Service Layer: Business logic separated from HTTP layer
- Dependency Injection: Database session injected via FastAPI Depends()
- Transaction Safety: All operations within async context managers
- Security: Secure random password generation, bcrypt hashing
"""

import logging
import secrets
import string
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import get_password_hash
from app.models.user import User

logger = logging.getLogger(__name__)


class UserImportService:
    """Service for importing users from Google Sheets data.

    Provides methods for creating user accounts from reviewer data,
    with automatic username generation, secure password creation,
    and role mapping.
    """

    @staticmethod
    def generate_secure_password(length: int = 16) -> str:
        """Generate a cryptographically secure random password.

        Password includes uppercase, lowercase, digits, and special characters
        to meet security requirements.

        Args:
            length: Password length (default: 16)

        Returns:
            Secure random password

        Example:
            >>> password = UserImportService.generate_secure_password()
            >>> len(password) >= 16
            True
        """
        # Character sets for password
        uppercase = string.ascii_uppercase
        lowercase = string.ascii_lowercase
        digits = string.digits
        special = "!@#$%^&*()_+-=[]{}|"

        # Ensure at least one character from each set
        password_chars = [
            secrets.choice(uppercase),
            secrets.choice(lowercase),
            secrets.choice(digits),
            secrets.choice(special),
        ]

        # Fill remaining length with random characters from all sets
        all_chars = uppercase + lowercase + digits + special
        password_chars.extend(secrets.choice(all_chars) for _ in range(length - 4))

        # Shuffle to avoid predictable patterns
        password_list = list(password_chars)
        secrets.SystemRandom().shuffle(password_list)

        return "".join(password_list)

    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """Get user by email address.

        Args:
            db: Database session
            email: Email address (case-insensitive)

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(
            select(User).where(User.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
        """Get user by username.

        Args:
            db: Database session
            username: Username (case-sensitive)

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(
            select(User).where(User.username == username.strip())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_curator_from_reviewer(
        db: AsyncSession,
        email: str,
        username: str,
        full_name: Optional[str] = None,
        role: str = "curator",
        orcid: Optional[str] = None,
    ) -> User:
        """Create or update curator user from reviewer data.

        If a user with the email already exists, updates their information.
        Otherwise, creates a new user with a secure random password.

        Args:
            db: Database session
            email: Email address (will be normalized to lowercase)
            username: Username for login
            full_name: Full name (optional)
            role: User role (default: "curator")
            orcid: ORCID identifier (optional)

        Returns:
            User object (newly created or updated)

        Raises:
            ValueError: If username is already taken by a different user

        Example:
            >>> async with get_db() as db:
            ...     user = await UserImportService.create_curator_from_reviewer(
            ...         db=db,
            ...         email="john.doe@example.com",
            ...         username="john_doe",
            ...         full_name="John Doe",
            ...         orcid="0000-0001-2345-6789"
            ...     )
            ...     await db.commit()
        """
        # Normalize email
        email_normalized = email.strip().lower()

        # Check if user with this email already exists
        existing_user = await UserImportService.get_user_by_email(db, email_normalized)

        if existing_user:
            logger.info(
                f"User with email {email_normalized} already exists "
                f"(id={existing_user.id}), updating information"
            )

            # Update user information
            if full_name:
                existing_user.full_name = full_name
            if role and existing_user.role != role:
                logger.info(
                    f"Updating role for {email_normalized}: "
                    f"{existing_user.role} -> {role}"
                )
                existing_user.role = role

            return existing_user

        # Check if username is already taken
        existing_username = await UserImportService.get_user_by_username(db, username)
        if existing_username:
            raise ValueError(
                f"Username '{username}' is already taken by user "
                f"{existing_username.email} (id={existing_username.id})"
            )

        # Generate secure random password
        # User should change on first login
        temp_password = UserImportService.generate_secure_password()
        hashed_password = get_password_hash(temp_password)

        # Create new user
        new_user = User(
            email=email_normalized,
            username=username,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=True,  # Reviewers are pre-verified
        )

        db.add(new_user)
        await db.flush()  # Get ID without committing transaction

        logger.info(
            f"Created new user: {username} ({email_normalized}) "
            f"with role={role}, id={new_user.id}"
        )
        logger.warning(
            f"IMPORTANT: Temporary password generated for {email_normalized}. "
            f"User should change password on first login."
        )

        # Note: We don't log the actual password for security
        # In a real system, this would be sent via secure email

        return new_user

    @staticmethod
    async def create_or_update_curator_batch(
        db: AsyncSession,
        reviewer_data_list: list[dict],
    ) -> list[User]:
        """Create or update multiple curator users in a batch.

        This is more efficient than calling create_curator_from_reviewer
        multiple times individually.

        Args:
            db: Database session
            reviewer_data_list: List of dicts with reviewer data
                Each dict should have keys: email, username, full_name, role, orcid

        Returns:
            List of User objects (created or updated)

        Example:
            >>> reviewers = [
            ...     {
            ...         "email": "john.doe@example.com",
            ...         "username": "john_doe",
            ...         "full_name": "John Doe",
            ...         "role": "curator",
            ...         "orcid": "0000-0001-2345-6789"
            ...     },
            ...     ...
            ... ]
            >>> users = await UserImportService.create_or_update_curator_batch(
            ...     db=db,
            ...     reviewer_data_list=reviewers
            ... )
        """
        users = []

        for reviewer_data in reviewer_data_list:
            try:
                user = await UserImportService.create_curator_from_reviewer(
                    db=db,
                    email=reviewer_data["email"],
                    username=reviewer_data["username"],
                    full_name=reviewer_data.get("full_name"),
                    role=reviewer_data.get("role", "curator"),
                    orcid=reviewer_data.get("orcid"),
                )
                users.append(user)
            except ValueError as e:
                logger.error(
                    f"Failed to create/update user {reviewer_data.get('email')}: {e}"
                )
                # Continue with other users instead of failing entire batch
                continue

        logger.info(
            f"Batch import complete: {len(users)} users created/updated "
            f"out of {len(reviewer_data_list)} reviewer records"
        )

        return users
