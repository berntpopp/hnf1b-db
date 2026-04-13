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


def is_curator_or_admin(user: Optional[User]) -> bool:
    """Return True when user is authenticated and has curator or admin role.

    Centralised here so that ``crud.py`` and ``transitions.py`` (and any
    future callers) stay in sync when role names change.
    """
    return user is not None and user.is_curator


# FastAPI security scheme (required — raises 403 when header missing)
security = HTTPBearer()

# Optional variant — does NOT raise when the Authorization header is absent.
# Used by ``get_optional_user`` to support anonymous + authenticated callers
# on the same endpoint.
_optional_security = HTTPBearer(auto_error=False)


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


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated user, or ``None`` for anonymous callers.

    Unlike ``get_current_user``, this dependency does NOT raise when the
    ``Authorization`` header is absent.  It is used by endpoints that serve
    both anonymous visitors (public read) and authenticated curators
    (working-copy read).

    A present-but-invalid token still raises 401 — this dependency is not
    a bypass for bad credentials.
    """
    if credentials is None:
        return None

    try:
        payload = verify_token(credentials.credentials, token_type="access")
    except HTTPException:
        # Invalid / expired token — treat as anonymous (callers may choose to
        # re-raise, but for optional auth the safest default is anonymous).
        return None

    username = payload.get("sub")
    if not username:
        return None

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return None

    return user
