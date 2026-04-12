"""Authentication and authorization module."""

from app.auth.dependencies import get_current_user, require_admin, require_curator
from app.auth.email import ConsoleEmailSender, EmailSender, get_email_sender
from app.auth.password import (
    get_password_hash,
    validate_password_strength,
    verify_and_update_password_hash,
    verify_password,
)
from app.auth.permissions import Role, get_role_permissions
from app.auth.tokens import create_access_token, create_refresh_token, verify_token

__all__ = [
    # Dependencies
    "get_current_user",
    "require_admin",
    "require_curator",
    # Email
    "EmailSender",
    "ConsoleEmailSender",
    "get_email_sender",
    # Password
    "get_password_hash",
    "validate_password_strength",
    "verify_and_update_password_hash",
    "verify_password",
    # Permissions
    "Role",
    "get_role_permissions",
    # Tokens
    "create_access_token",
    "create_refresh_token",
    "verify_token",
]
