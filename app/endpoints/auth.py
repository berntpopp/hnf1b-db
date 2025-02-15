# File: app/endpoints/auth.py
import jwt
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from app.config import settings
from app.database import db
from app.models import User

router = APIRouter()

# Set up password hashing using bcrypt.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Return a bcrypt hash of the password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, stored_password: str) -> bool:
    """
    Verify the provided password.
    
    If the stored password does not appear to be a bcrypt hash (i.e. it doesn't start with "$2"),
    fall back to a plain-text comparison. This allows you to use your existing users while you
    transition to hashed passwords.
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
    """
    Create a JWT token including an expiration time.
    
    Args:
        data: The payload data (e.g. {"sub": "username"}).
        expires_delta: Optional timedelta for token expiration.
        
    Returns:
        A JWT token as a string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Define the OAuth2 scheme. The token URL must match the login endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

# Pydantic model for new user registration.
class UserCreate(BaseModel):
    user_id: int
    user_name: str
    password: str
    email: EmailStr
    user_role: str
    first_name: str
    family_name: str
    orcid: str = None
    abbreviation: str

@router.post("/register", summary="Register a new user")
async def register(user: UserCreate):
    """
    Register a new user.
    
    - Checks if a user with the provided email already exists.
    - Hashes the provided password before storing.
    """
    existing = await db.users.find_one({"email": user.email})
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")
    
    user_dict = user.dict()
    # Hash the password before storing it.
    user_dict["password"] = hash_password(user.password)
    
    result = await db.users.insert_one(user_dict)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail="User registration failed")
    return {"msg": "User registered successfully"}

@router.post("/token", summary="Login and obtain a JWT token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Login endpoint.
    
    This endpoint expects form data with the following fields:
      - **username**: Your username.
      - **password**: Your plain text password.
      - **scope**: (Optional) Space-separated scopes.
      - **client_id**: (Optional)
      - **client_secret**: (Optional)
    
    It validates the credentials against the database and returns a JWT token if successful.
    """
    user_doc = await db.users.find_one({"user_name": form_data.username})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, user_doc["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user_doc["user_name"]})
    return {"access_token": access_token, "token_type": "bearer"}

def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Dependency to retrieve the current user based on the JWT token.
    
    Raises HTTP 401 if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: no subject")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    return username

@router.get("/me", summary="Get current user info")
async def read_users_me(current_user: str = Depends(get_current_user)):
    """
    Return the current user's username (extracted from the JWT token).
    
    In a real application, you might look up and return additional user data.
    """
    return {"user": current_user}
