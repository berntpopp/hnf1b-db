"""Dev-only quick-login router — NEVER MOUNTED IN PRODUCTION.

Wave 5a Layer 2 of the dev-mode 5-layer defense (platform review §5.3).

This module exposes ``POST /api/v2/dev/login-as/{username}`` which mints
access + refresh tokens for a fixture user (``is_fixture_user=True``)
WITHOUT verifying a password. It exists solely so local developers and
automated UI tests can swap between seeded personas without juggling
plaintext credentials.

Five layers of defense protect this endpoint from reaching production:

1. **Config refusal** (``app/core/config.py``): ``Settings`` refuses to
   instantiate when ``ENABLE_DEV_AUTH=true`` and ``ENVIRONMENT`` is not
   ``development``. An unset environment is treated as production.
2. **Module-level assert** (this file): the module body contains an
   ``assert settings.enable_dev_auth and settings.environment ==
   "development"`` which crashes on any accidental import outside dev
   mode. Do NOT remove it.
3. **Conditional router mount** (``app/main.py``): ``main.py`` only
   imports this module and calls ``include_router`` when the same two
   flags are set, so in production the module is never imported at all.
4. **Fixture-user gate** (``app/models/user.User.is_fixture_user``): the
   endpoint below refuses to mint tokens for any user whose
   ``is_fixture_user`` column is ``False``. Production user rows have
   ``is_fixture_user=False`` and the seed script that flips it to
   ``True`` will be added in Task 10.
5. **Loopback-only guard** (``_require_loopback``): even inside a dev
   build the endpoint refuses any request whose ``client.host`` is not
   ``127.0.0.1`` / ``::1`` / ``localhost`` / ``testclient``. A leaked
   dev build exposed on a LAN interface cannot be exploited over the
   network.

Layers 4 (frontend build-time DCE) and 5 (CI grep on prod bundles) are
implemented in Tasks 11 and 12 of the Wave 5a foundations plan.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.tokens import create_access_token, create_refresh_token
from app.core.config import settings
from app.database import get_db
from app.repositories.user_repository import UserRepository
from app.schemas.auth import Token

logger = logging.getLogger(__name__)

# --- Layer 2: hard runtime assert ------------------------------------------
#
# Belt-and-braces for the import gate in ``main.py``. If any code path ever
# imports this module with the wrong flags, CRASH — do not silently register
# a production-facing dev router. Removing this assert defeats Layer 2 of the
# dev-mode defense; please don't.
assert settings.enable_dev_auth and settings.environment == "development", (
    "app.api.dev_endpoints imported outside of dev mode — refusing to load. "
    "This module must only be imported when ENABLE_DEV_AUTH=true and "
    "ENVIRONMENT=development. If you are seeing this during a production "
    "boot, investigate app/main.py's conditional mount immediately."
)

router = APIRouter(
    prefix="/api/v2/dev",
    tags=["dev-only"],
    include_in_schema=False,
)

# Hosts that count as loopback for Layer 5. ``testclient`` is the default
# ``client.host`` value set by Starlette's ASGI test transport, so httpx-based
# tests sail through without us having to spoof headers.
_LOOPBACK_HOSTS: frozenset[str] = frozenset(
    {"127.0.0.1", "::1", "localhost", "testclient"}
)


def _require_loopback(request: Request) -> None:
    """Reject any request whose remote address is not loopback.

    FastAPI dependency form so the check runs before the route handler body
    and composes with ``Depends(get_db)``. Raises ``HTTPException(403)`` on
    non-loopback origins so a misconfigured reverse proxy or leaked dev
    build cannot be exploited over the network.
    """
    client_host = request.client.host if request.client else None
    if client_host not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="dev-mode login is loopback-only",
        )


@router.post("/login-as/{username}", response_model=Token)
async def dev_login_as(
    username: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_require_loopback),
) -> Token:
    """Mint fresh tokens for a seeded fixture user — NO password check.

    Layer 3 (partial) of the dev-mode defense: the endpoint looks up the
    user by ``username`` and refuses to mint anything unless
    ``is_fixture_user`` is ``True``. The ``admin`` row created by
    ``make db-create-admin`` has ``is_fixture_user=False`` so the real
    admin cannot be hijacked by this endpoint even in dev mode.
    """
    repo = UserRepository(db)
    user = await repo.get_by_username(username)

    if user is None or not user.is_fixture_user:
        # Same 404 response whether the user is missing or simply not a
        # fixture — no point leaking which is which on a dev-only surface.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not a fixture user",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="inactive fixture user",
        )

    access_token = create_access_token(
        subject=user.username,
        role=user.role,
        permissions=user.get_permissions(),
    )
    refresh_token = create_refresh_token(subject=user.username)
    await repo.update_refresh_token(user, refresh_token)

    logger.warning(
        "DEV LOGIN as %s from %s",
        username,
        request.client.host if request.client else "unknown",
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
