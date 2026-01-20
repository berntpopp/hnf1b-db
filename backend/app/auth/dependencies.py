"""FastAPI dependencies for authentication and authorization."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import verify_token
from app.database import get_db
from app.models.user import User

# FastAPI security scheme
security = HTTPBearer()

# Optional security scheme - does not auto-error if no token provided
optional_security = HTTPBearer(auto_error=False)


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


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None.

    This dependency is for endpoints that work for both authenticated and
    unauthenticated users, but want to optionally track authenticated access.

    Unlike get_current_user, this dependency:
    - Does NOT raise 401 if no token is provided
    - Does NOT raise 401 if token is invalid or expired
    - Returns None for any authentication failure
    - Returns the User only if token is valid and user is active

    Args:
        credentials: Optional bearer token from Authorization header
        db: Database session

    Returns:
        User model instance if authenticated, None otherwise
    """
    # No token provided - anonymous access
    if credentials is None:
        return None

    try:
        # Verify and decode token
        token = credentials.credentials
        payload = verify_token(token, token_type="access")

        # Extract username from token
        username = payload.get("sub")
        if not username:
            return None

        # Fetch user from database
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            return None

        if not user.is_active:
            return None

        # Check account lockout
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            return None

        return user

    except HTTPException:
        # Token verification failed (invalid, expired, wrong type)
        return None
    except Exception:
        # Any other error - fail silently for optional auth
        return None
