"""Wave 5b Task 7: BOPLA — UserUpdatePublic must exclude privilege-escalation fields.

Closes scope doc row F-top-1. The original UserUpdate schema allowed
role and is_active as optional fields, which was safe in practice
because only the admin update_user endpoint accepted it. Rename to
UserUpdateAdmin to make intent explicit, and add UserUpdatePublic
which structurally excludes role, is_active, is_superuser,
refresh_token, hashed_password, and is_fixture_user.

This test is the durable contract: any future developer who tries to
add a field to UserUpdatePublic that would enable privilege escalation
fails this test.
"""

from __future__ import annotations


def test_user_update_public_excludes_dangerous_fields():
    """UserUpdatePublic.model_fields must not contain role, is_active, etc."""
    from app.schemas.auth import UserUpdatePublic

    forbidden = {
        "role",
        "is_active",
        "is_superuser",
        "is_verified",
        "is_fixture_user",
        "hashed_password",
        "refresh_token",
        "failed_login_attempts",
        "locked_until",
        "permissions",
    }
    allowed = set(UserUpdatePublic.model_fields.keys())
    overlap = allowed & forbidden
    assert overlap == set(), (
        f"UserUpdatePublic leaks privilege-escalation fields: {overlap}. "
        f"Any user-facing update endpoint MUST use UserUpdatePublic, "
        f"not UserUpdateAdmin."
    )


def test_user_update_admin_preserves_existing_admin_fields():
    """UserUpdateAdmin keeps all fields the admin UI needs to edit."""
    from app.schemas.auth import UserUpdateAdmin

    required = {"email", "password", "full_name", "role", "is_active"}
    present = set(UserUpdateAdmin.model_fields.keys())
    missing = required - present
    assert missing == set(), f"UserUpdateAdmin missing admin-required fields: {missing}"


def test_user_update_old_name_is_removed():
    """The old `UserUpdate` name must no longer exist — all imports updated."""
    import app.schemas.auth as auth_schemas

    assert not hasattr(auth_schemas, "UserUpdate"), (
        "UserUpdate must be renamed to UserUpdateAdmin — no back-compat alias. "
        "See Wave 5b Task 7."
    )


def test_token_schema_allows_access_token_only_response():
    """Token responses must support access-token-only auth contracts."""
    from app.schemas.auth import Token

    token = Token(
        access_token="access-token",
        token_type="bearer",
        expires_in=1800,
    )

    assert token.access_token == "access-token"
    assert token.refresh_token is None
