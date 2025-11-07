"""Authentication endpoints."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    Token,
    UserLogin,
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix="/api/v2/auth", tags=["authentication"])


# Simple in-memory user store for demonstration
# In production, this should be in the database
DEMO_USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": get_password_hash("admin123"),
        "role": "admin",
    },
    "researcher": {
        "username": "researcher",
        "hashed_password": get_password_hash("research123"),
        "role": "researcher",
    },
}


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    """Authenticate user and return JWT token."""
    # Check if user exists in demo users
    user = DEMO_USERS.get(user_data.username)

    if not user or not verify_password(user_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]},
        expires_delta=access_token_expires,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user_info(current_user=Depends(get_current_user)):
    """Get current user information."""
    return {"username": current_user.username}


@router.post("/logout")
async def logout():
    """Logout endpoint (client should remove token)."""
    return {"message": "Successfully logged out"}
