"""Authentication API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    require_admin,
    verify_password,
    verify_token,
)
from app.auth.permissions import get_all_roles
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    PasswordChange,
    RefreshTokenRequest,
    RoleResponse,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.utils.audit_logger import log_user_action

router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Login with username and password.

    Returns JWT access token and refresh token.

    **Security:**
    - Password verified with bcrypt
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

    # Verify password
    if not user or not verify_password(credentials.password, user.hashed_password):
        # Record failed attempt if user exists
        if user:
            await repo.record_failed_login(user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    # Check if account is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Create tokens
    access_token = create_access_token(user.username, user.role, user.get_permissions())
    refresh_token = create_refresh_token(user.username)

    # Update user record
    await repo.record_successful_login(user)
    await repo.update_refresh_token(user, refresh_token)

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

    # Verify stored refresh token matches (token rotation)
    if user.refresh_token != request.refresh_token:
        # Possible token theft - invalidate all tokens
        await repo.update_refresh_token(user, "")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Create new tokens (rotation)
    new_access_token = create_access_token(
        user.username, user.role, user.get_permissions()
    )
    new_refresh_token = create_refresh_token(user.username)

    # Store new refresh token
    await repo.update_refresh_token(user, new_refresh_token)

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
    await repo.update(
        current_user,
        UserUpdate(
            password=password_data.new_password,
            email=None,
            full_name=None,
            role=None,
            is_active=None,
        ),
    )

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


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
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


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    role: str | None = None,
    current_user: User = Depends(require_admin),
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


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
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


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
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


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
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

    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    await log_user_action(
        db=db,
        user_id=user_id,
        action="USER_DELETED",
        details=f"Admin '{current_user.username}' deleted user '{user.username}'",
    )

    await repo.delete(user)
