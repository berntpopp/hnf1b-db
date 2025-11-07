"""Password hashing and validation utilities."""

from passlib.context import CryptContext

from app.config import settings

# Bcrypt password context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash.

    Args:
        plain_password: Plain text password
        hashed_password: Bcrypt hash

    Returns:
        True if password matches hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def validate_password_strength(password: str) -> None:
    """Validate password meets security requirements.

    Args:
        password: Password to validate

    Raises:
        ValueError: If password doesn't meet requirements with detailed message
    """
    errors = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Must be at least {settings.PASSWORD_MIN_LENGTH} characters")

    if not any(c.isupper() for c in password):
        errors.append("Must contain uppercase letter")

    if not any(c.islower() for c in password):
        errors.append("Must contain lowercase letter")

    if not any(c.isdigit() for c in password):
        errors.append("Must contain digit")

    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        errors.append("Must contain special character")

    if errors:
        raise ValueError(f"Password validation failed: {'; '.join(errors)}")
