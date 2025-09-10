# File: app/endpoints/auth.py
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from app.config import settings
from app.dependencies import get_user_repository
from app.repositories import UserRepository

router = APIRouter()

# Set up password hashing using bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, stored_password: str) -> bool:
    """Verify the provided password.

    If the stored password does not appear to be a bcrypt hash (i.e. it doesn't
    start with "$2"), fall back to a plain-text comparison. This allows you to
    use your existing users while you transition to hashed passwords.
    """
    if not stored_password.startswith("$2"):
        # Fallback: plain text comparison (insecure)
        return plain_password == stored_password
    return pwd_context.verify(plain_password, stored_password)


# JWT settings.
SECRET_KEY = settings.JWT_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Create a JWT token including an expiration time.

    Args:
        data: The payload data (e.g. {"sub": "username"}).
        expires_delta: Optional timedelta for token expiration.

    Returns:
        A JWT token as a string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Define the OAuth2 scheme. The token URL must match the login endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# Pydantic models for authentication
class Token(BaseModel):
    """Response model for successful authentication."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds


class UserResponse(BaseModel):
    """User information response model."""
    user_id: int
    user_name: str
    email: str
    user_role: str
    first_name: str
    family_name: str
    orcid: str | None = None

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    """Pydantic model for new user registration."""
    user_id: int
    user_name: str
    password: str
    email: EmailStr
    user_role: str
    first_name: str
    family_name: str
    orcid: str = None
    abbreviation: str


@router.post("/token", response_model=Token, summary="Login and obtain a JWT token")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """Authenticate user and return JWT token.

    This endpoint follows the OAuth2 password flow specification:
      - **username**: Your username (user_name field)
      - **password**: Your plain text password
      - **scope**: (Optional) Space-separated scopes (currently ignored)
      - **client_id**: (Optional, currently ignored)
      - **client_secret**: (Optional, currently ignored)

    Returns:
        Token: JWT access token with expiration information

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Authenticate user against PostgreSQL database
    user = await user_repo.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT token with user information
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_name, "user_id": user.user_id, "role": user.user_role},
        expires_delta=access_token_expires,
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    """Dependency to retrieve the current user from JWT token.

    Args:
        token: JWT token from Authorization header
        user_repo: User repository for database operations

    Returns:
        UserResponse: Current user information

    Raises:
        HTTPException: 401 if token is invalid, expired, or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    # Verify user still exists in database
    user = await user_repo.get_by_username(username)
    if user is None:
        raise credentials_exception

    return UserResponse.model_validate(user)


@router.get("/me", response_model=UserResponse, summary="Get current user info")
async def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    """Return the current user's information from JWT token.

    This endpoint requires a valid JWT token in the Authorization header.
    Returns complete user profile information.

    Returns:
        UserResponse: Current authenticated user's profile data
    """
    return current_user
