"""Password hashing and verification via pwdlib.

Wave 5b Task 11 (scope doc F-top-3): replaces the passlib CryptContext
with pwdlib.  The hasher stack uses Argon2Hasher as primary and
BcryptHasher as fallback verifier, so legacy ``$2b$...`` hashes verify
cleanly and transparently upgrade to Argon2id on the first successful
login after deploy via ``verify_and_update_password_hash()``.
"""

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# Argon2id primary, bcrypt fallback verifier for legacy hashes.
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))


def get_password_hash(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Argon2id hashed password
    """
    return _password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash (Argon2id or legacy bcrypt).

    Args:
        plain_password: Plain text password
        hashed_password: Argon2id or legacy bcrypt hash

    Returns:
        True if password matches hash
    """
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False


def verify_and_update_password_hash(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    """Verify a password and return a new hash if the stored one is legacy.

    Uses pwdlib's built-in ``verify_and_update`` which returns a new
    Argon2id hash when the input was verified against a non-primary
    hasher (i.e. the BcryptHasher fallback).

    Args:
        plain_password: Plain text password
        hashed_password: Stored hash (Argon2id or legacy bcrypt)

    Returns:
        ``(valid, new_hash)`` -- *new_hash* is not ``None`` only when
        verification succeeded AND the stored hash needs upgrading to
        Argon2id.
    """
    try:
        return _password_hash.verify_and_update(plain_password, hashed_password)
    except Exception:
        return False, None


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
