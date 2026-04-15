"""Authentication API endpoints."""

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    require_admin,
    verify_and_update_password_hash,
    verify_password,
    verify_token,
)
from app.auth.credential_tokens import CredentialTokenService
from app.auth.email import get_email_sender
from app.auth.permissions import get_all_roles
from app.auth.rate_limit import RateLimiter
from app.core.config import settings
from app.database import get_db
from app.models.credential_token import CredentialToken
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    InviteAcceptRequest,
    InviteRequest,
    InviteResponse,
    MessageResponse,
    PasswordChange,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RoleResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdateAdmin,
    UserUpdatePublic,
)
from app.utils.audit_logger import log_user_action

logger = logging.getLogger(__name__)


def _assert_user_can_receive_tokens(user: User) -> None:
    """Reject inactive or currently locked users before token issuance."""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {user.locked_until.isoformat()}",
        )


def _frontend_base_url() -> str:
    """Return the first CORS origin, stripped, for email link construction.

    Centralizes the helper so every identity-lifecycle email uses the
    same base URL resolution (CORS_ORIGINS can contain spaces after
    commas in env vars — split + strip is not automatic).
    """
    origins = settings.get_cors_origins_list()
    return origins[0] if origins else ""


async def _safe_send_email(
    *, to: str, subject: str, body_html: str, context: str
) -> None:
    """Dispatch email via configured sender, swallowing + logging errors.

    Email dispatch must never leak user-existence (anti-enumeration in
    password reset flow) nor block an already-committed DB write (admin
    create-user, invite). Callers always commit the token row BEFORE
    calling this helper — a failed email never rolls back state.
    """
    try:
        sender = get_email_sender()
        await sender.send(to=to, subject=subject, body_html=body_html)
    except Exception as exc:  # noqa: BLE001 — intentional catch-all
        logger.error(
            "Email dispatch failed",
            extra={"context": context, "to": to, "error": str(exc)},
        )


router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])

# Wave 5b Task 9: admin user-management routes live on a sub-router
# with router-level require_admin dependency.  The BFLA matrix in
# test_admin_route_authorization.py asserts every /auth/users/* route
# denies non-admins regardless of per-endpoint guards.
users_router = APIRouter(
    prefix="/users",
    dependencies=[Depends(require_admin)],
    tags=["user-management"],
)


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Login with username and password.

    Returns JWT access token and refresh token.

    **Security:**
    - Password verified with Argon2id (or legacy bcrypt via fallback)
    - Legacy bcrypt hashes transparently upgrade to Argon2id on login
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

    # Wave 5b Task 11: verify + transparent legacy-hash upgrade.
    # verify_and_update_password_hash returns (valid, new_hash) where
    # new_hash is not None only when verification succeeded AND the
    # stored hash was legacy bcrypt that needs upgrading to Argon2id.
    valid, new_hash = (
        verify_and_update_password_hash(credentials.password, user.hashed_password)
        if user
        else (False, None)
    )
    if not user or not valid:
        # Record failed attempt if user exists
        if user:
            await repo.record_failed_login(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Transparent rehash: if the stored hash was legacy bcrypt, write
    # the new Argon2id hash back. No forced logout, no user-visible change.
    if new_hash is not None:
        user.hashed_password = new_hash
        await db.flush()

    _assert_user_can_receive_tokens(user)

    # Create tokens
    access_token = create_access_token(user.username, user.role, user.get_permissions())
    refresh_token = create_refresh_token(
        user.username, session_version=user.session_version
    )

    # Update user record
    await repo.record_successful_login(user)
    await repo.update_refresh_token(user, refresh_token)
    await db.commit()

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

    _assert_user_can_receive_tokens(user)

    # Verify stored refresh token matches (token rotation)
    if user.refresh_token != request.refresh_token:
        # Possible token theft - invalidate all tokens
        await repo.update_refresh_token(user, "")
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Create new tokens (rotation)
    new_access_token = create_access_token(
        user.username, user.role, user.get_permissions()
    )
    new_refresh_token = create_refresh_token(
        user.username, session_version=user.session_version
    )

    # Store new refresh token
    await repo.update_refresh_token(user, new_refresh_token)
    await db.commit()

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
    await db.commit()

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
    if not verify_password(
        password_data.current_password, current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Update password
    repo = UserRepository(db)
    user_update = UserUpdatePublic(password=password_data.new_password)  # type: ignore[call-arg]  # mypy+pydantic: Field(None) defaults not recognized
    await repo.update(current_user, user_update)
    await repo.update_refresh_token(current_user, "")
    await db.commit()

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


@users_router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user),
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
        details=(
            f"Admin '{current_user.username}' created user "
            f"'{user.username}' with role '{user.role}'"
        ),
    )

    # Auto-dispatch email verification (Wave 5c Task 8).
    # Token is committed before email dispatch; email errors are logged
    # but do not fail the create-user response (Copilot PR #235 review).
    token_svc = CredentialTokenService(db)
    raw_token, _ = await token_svc.create_token(
        purpose="verify",
        email=user.email,
        user_id=user.id,
    )

    verify_url = f"{_frontend_base_url()}/verify-email/{raw_token}"
    await _safe_send_email(
        to=user.email,
        subject=f"Verify your email - {settings.email.from_name}",
        body_html=f"<p>Verify your email: {verify_url}</p>",
        context="create_user.verify_email",
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


@users_router.get("", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = None,
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


@users_router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
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


@users_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdateAdmin,
    current_user: User = Depends(get_current_user),
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

    # Wave 5b: block ALL mutations on the _system_migration_ placeholder.
    # This user is the ON DELETE SET NULL fallback for audit-actor FKs —
    # changing its role, deactivating it, or editing its email could
    # break the FK constraint or make audit rows unresolvable.
    if user.username == "_system_migration_":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot modify the _system_migration_ placeholder user — "
                "it is the audit-actor FK fallback from the Wave 5a data "
                "migration and must remain unchanged."
            ),
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


@users_router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
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

    # Wave 5b Task 14: protect the _system_migration_ placeholder user
    if user.username == "_system_migration_":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot delete the _system_migration_ placeholder user — "
                "it is the ON DELETE SET NULL fallback for audit-actor FKs "
                "from the Wave 5a data migration."
            ),
        )

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    # Wave 5c Task 8: remove credential tokens referencing this user to
    # avoid FK violations (invite/reset/verify tokens are meaningless
    # after the user is deleted). The FK on credential_tokens.user_id
    # does not specify ON DELETE; cleaning up here keeps the deletion
    # atomic without requiring a schema migration.
    await db.execute(
        sa_delete(CredentialToken).where(CredentialToken.user_id == user.id)
    )

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_DELETED",
        details=f"Admin '{current_user.username}' deleted user '{user.username}'",
    )

    await repo.delete(user)


@users_router.patch("/{user_id}/unlock", response_model=UserResponse)
async def unlock_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Unlock a user account (admin only).

    Wave 5b Task 6: clears ``failed_login_attempts`` and ``locked_until``
    so a user who tripped the 5-failed-attempts / 15-minute lockout can
    log in again without waiting for the window to expire.

    **Returns:**
    - 200: User unlocked successfully
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

    unlocked = await repo.unlock(user)

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_UNLOCKED",
        details=(f"Admin '{current_user.username}' unlocked user '{user.username}'"),
    )

    return UserResponse(
        id=unlocked.id,
        username=unlocked.username,
        email=unlocked.email,
        full_name=unlocked.full_name,
        role=unlocked.role,
        permissions=unlocked.get_permissions(),
        is_active=unlocked.is_active,
        is_verified=unlocked.is_verified,
        last_login=unlocked.last_login,
        created_at=unlocked.created_at,
        updated_at=unlocked.updated_at,
    )


@users_router.post(
    "/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED
)
async def create_invite(
    invite_data: InviteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InviteResponse:
    """Invite a new user by email (admin only).

    Creates a credential token bound to the target email.
    Re-inviting the same email invalidates prior invite tokens.
    """
    token_svc = CredentialTokenService(db)

    # Invalidate any existing invite tokens for this email
    await token_svc.invalidate_by_email_and_purpose(
        email=invite_data.email, purpose="invite"
    )

    raw_token, db_token = await token_svc.create_token(
        purpose="invite",
        email=invite_data.email,
        metadata={"role": invite_data.role},
    )

    # URL-encode email query param — addresses with '+' or reserved
    # characters would otherwise produce broken links (Copilot PR #235).
    accept_url = (
        f"{_frontend_base_url()}/accept-invite/{raw_token}"
        f"?{urlencode({'email': invite_data.email})}"
    )
    await _safe_send_email(
        to=invite_data.email,
        subject=f"You've been invited to {settings.email.from_name}",
        body_html=(
            f"<p>You've been invited as a {invite_data.role}. "
            f'Click here to accept: <a href="{accept_url}">{accept_url}</a></p>'
        ),
        context="invite.dispatch",
    )

    await log_user_action(
        db=db,
        user_id=current_user.id,
        action="USER_INVITED",
        details=(
            f"Admin '{current_user.username}' invited "
            f"'{invite_data.email}' as {invite_data.role}"
        ),
    )

    response = InviteResponse(
        email=invite_data.email,
        role=invite_data.role,
        expires_at=db_token.expires_at,
    )

    # Dev-only: include raw token for testing
    if settings.environment != "production":
        response.token = raw_token

    return response


@router.post(
    "/invite/accept/{token}",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter("invite-accept", 5, 3600))],
)
async def accept_invite(
    token: str,
    accept_data: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Accept an invite and create a user account.

    The user is created with is_verified=True (email ownership proved
    by receiving the invite).
    """
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="invite")

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used invite token.",
        )

    repo = UserRepository(db)

    # Check username uniqueness
    if await repo.get_by_username(accept_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{accept_data.username}' already exists",
        )

    # Check email uniqueness
    if await repo.get_by_email(db_token.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{db_token.email}' already exists",
        )

    # Extract role from token metadata
    role = (db_token.metadata_ or {}).get("role", "viewer")

    # Create user
    user = User(
        username=accept_data.username,
        email=db_token.email,
        hashed_password=get_password_hash(accept_data.password),
        full_name=accept_data.full_name,
        role=role,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await log_user_action(
        db=db,
        user_id=user.id,
        action="INVITE_ACCEPTED",
        details=f"User '{user.username}' accepted invite for '{db_token.email}'",
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


@router.post(
    "/password-reset/request",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter("reset-request", 3, 3600))],
)
async def request_password_reset(
    reset_data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Request a password reset email.

    Always returns 202 regardless of whether the email exists —
    constant-time anti-enumeration per OWASP Forgot Password Cheat Sheet.
    """
    repo = UserRepository(db)
    user = await repo.get_by_email(reset_data.email)

    raw_token = None
    if user:
        token_svc = CredentialTokenService(db)
        await token_svc.invalidate_by_email_and_purpose(
            email=reset_data.email, purpose="reset"
        )
        raw_token, _ = await token_svc.create_token(
            purpose="reset",
            email=reset_data.email,
            user_id=user.id,
        )

        # Email errors MUST NOT leak user existence (OWASP anti-enum).
        # Swallow + log via _safe_send_email (Copilot PR #235 review).
        reset_url = f"{_frontend_base_url()}/reset-password/{raw_token}"
        await _safe_send_email(
            to=reset_data.email,
            subject=f"Password Reset - {settings.email.from_name}",
            body_html=f"<p>Reset your password: {reset_url}</p>",
            context="password_reset.request",
        )

    response = MessageResponse(
        message="If an account exists with that email, a reset link has been sent."
    )
    if settings.environment != "production" and raw_token:
        response.token = raw_token

    return response


@router.post(
    "/password-reset/confirm/{token}",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter("reset-confirm", 5, 3600))],
)
async def confirm_password_reset(
    token: str,
    reset_data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Confirm a password reset with a valid token."""
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="reset")

    if db_token is None or db_token.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used reset token.",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(db_token.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User associated with this token no longer exists.",
        )

    user.hashed_password = get_password_hash(reset_data.new_password)
    user.refresh_token = ""
    await db.commit()

    # Invalidate all remaining reset tokens for this email
    await token_svc.invalidate_by_email_and_purpose(
        email=db_token.email, purpose="reset"
    )

    await log_user_action(
        db=db,
        user_id=user.id,
        action="PASSWORD_RESET",
        details=f"User '{user.username}' reset password via token",
    )

    return MessageResponse(message="Password reset successful.")


@router.post(
    "/verify-email/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RateLimiter("verify-resend", 3, 3600))],
)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Resend email verification (authenticated, unverified users only)."""
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified.",
        )

    token_svc = CredentialTokenService(db)
    await token_svc.invalidate_by_email_and_purpose(
        email=current_user.email, purpose="verify"
    )
    raw_token, _ = await token_svc.create_token(
        purpose="verify",
        email=current_user.email,
        user_id=current_user.id,
    )

    verify_url = f"{_frontend_base_url()}/verify-email/{raw_token}"
    await _safe_send_email(
        to=current_user.email,
        subject=f"Verify your email - {settings.email.from_name}",
        body_html=f"<p>Verify your email: {verify_url}</p>",
        context="verify_email.resend",
    )

    response = MessageResponse(message="Verification email sent.")
    if settings.environment != "production":
        response.token = raw_token
    return response


@router.post(
    "/verify-email/{token}",
    response_model=MessageResponse,
    dependencies=[Depends(RateLimiter("verify-email", 5, 3600))],
)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify email address using a credential token."""
    token_svc = CredentialTokenService(db)
    db_token = await token_svc.verify_and_consume(token, purpose="verify")

    if db_token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already-used verification token.",
        )

    # verify tokens are always created with user_id set (see create_user
    # and resend_verification above); user_id: int | None is only used
    # by the invite flow, which has its own endpoint.
    if db_token.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is not bound to a user.",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(db_token.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User associated with this token no longer exists.",
        )

    user.is_verified = True
    await db.commit()

    await log_user_action(
        db=db,
        user_id=user.id,
        action="EMAIL_VERIFIED",
        details=f"User '{user.username}' verified email '{db_token.email}'",
    )

    return MessageResponse(message="Email verified successfully.")


# Wave 5b Task 9: mount the admin user-management sub-router
router.include_router(users_router)
