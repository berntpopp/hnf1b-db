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
