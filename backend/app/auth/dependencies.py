"""FastAPI dependencies for authentication and authorization."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import verify_token
from app.core.config import settings
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


# D.2 comments ------------------------------------------------------------------


async def require_comment_author_or_admin(
    comment_id: int,
    current_user: User = Depends(require_curator),
    db: AsyncSession = Depends(get_db),
) -> User:
    """403 unless the caller authored the comment or is admin.

    The router MUST use this for DELETE; PATCH has an additional
    "author only (not admin)" check performed inline because the matrix
    forbids admin body edits.
    """
    from app.comments.service import CommentsService  # local import avoids cycle

    svc = CommentsService(db)
    comment = await svc.get_by_id(comment_id, include_deleted=True)
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    is_admin = current_user.role == "admin"
    if comment.author_id != current_user.id and not is_admin:
        raise HTTPException(status_code=403, detail="Author or admin only")
    return current_user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated user, or ``None`` for truly anonymous callers.

    Returns ``None`` **only** when no ``Authorization`` header is present.
    If an ``Authorization`` header is present, this dependency validates
    strictly — any validation failure (invalid token, expired, malformed,
    user not found, inactive, or locked) raises ``HTTPException(401)``,
    exactly the same as ``get_current_user``.

    This makes it safe to use on endpoints that allow anonymous access (list,
    detail, search, aggregations, …): a visitor with no header gets ``None``,
    but a caller who sends a broken token is rejected immediately rather than
    being silently downgraded to anonymous, which would mask auth bugs.

    If your endpoint *requires* authentication, use ``get_current_user``
    instead.
    """
    if not request.headers.get("Authorization"):
        return None

    # Header is present — validate strictly; propagate any 401 raised by
    # get_current_user rather than swallowing it.
    # _optional_security returns None only when the header is absent, which
    # we already ruled out above, so the assert is always satisfied.
    credentials = await _optional_security(request)
    assert credentials is not None  # header present → always non-None
    return await get_current_user(credentials=credentials, db=db)


async def require_csrf_token(request: Request) -> None:
    """Require a matching CSRF cookie and header for cookie-auth flows."""
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    header_token = request.headers.get("x-csrf-token")

    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
