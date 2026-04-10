"""Tests for backend/app/auth/tokens.py.

Covers: access token generation, refresh token generation, decode/verify,
expiry detection, signature validation, and token type distinction.
"""

import os
import time

# Ensure JWT_SECRET / ADMIN_PASSWORD / DATABASE_URL are set for the
# Settings import chain. The root backend/conftest.py also installs these,
# but setdefault keeps this module safe to import in isolation (e.g. when
# running a single test file via `pytest tests/test_auth_tokens.py`).
os.environ.setdefault("JWT_SECRET", "0" * 64)
os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test",
)

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from app.auth.tokens import (  # noqa: E402
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.core.config import settings  # noqa: E402


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_encoded_jwt_string(self):
        """Access token is a three-segment JWT string."""
        token = create_access_token(
            subject="user-1", role="VIEWER", permissions=["phenopacket:read"]
        )
        assert isinstance(token, str)
        # A JWT has three base64url segments separated by dots.
        assert token.count(".") == 2

    def test_payload_round_trips_via_verify_token(self):
        """verify_token returns the claims passed to create_access_token."""
        token = create_access_token(
            subject="alice", role="CURATOR", permissions=["phenopacket:write"]
        )
        payload = verify_token(token, token_type="access")
        assert payload["sub"] == "alice"
        assert payload["role"] == "CURATOR"
        assert payload["permissions"] == ["phenopacket:write"]
        assert payload["type"] == "access"

    def test_payload_contains_standard_claims(self):
        """Access tokens carry RFC 7519 standard claims (exp, iat, jti)."""
        token = create_access_token(subject="user-1", role="VIEWER", permissions=[])
        payload = verify_token(token, token_type="access")
        assert "exp" in payload
        assert "iat" in payload
        assert "jti" in payload
        assert payload["type"] == "access"

    def test_each_token_has_unique_jti(self):
        """Repeated calls produce tokens with distinct jti values."""
        token_a = create_access_token("user-1", "VIEWER", [])
        token_b = create_access_token("user-1", "VIEWER", [])
        payload_a = verify_token(token_a)
        payload_b = verify_token(token_b)
        assert payload_a["jti"] != payload_b["jti"]

    def test_expired_access_token_raises_401(self):
        """Expired tokens are rejected with HTTP 401."""
        past = int(time.time()) - 3600
        expired = jwt.encode(
            {
                "sub": "user-1",
                "exp": past,
                "iat": past - 60,
                "jti": "expired-jti",
                "type": "access",
                "role": "VIEWER",
                "permissions": [],
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            verify_token(expired, token_type="access")
        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_wrong_signature_raises_401(self):
        """Tokens signed with a different secret must be rejected."""
        forged = jwt.encode(
            {
                "sub": "user-1",
                "exp": int(time.time()) + 3600,
                "iat": int(time.time()),
                "jti": "forged-jti",
                "type": "access",
                "role": "VIEWER",
                "permissions": [],
            },
            "completely-wrong-secret",
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            verify_token(forged, token_type="access")
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self):
        """A non-JWT string must be rejected with HTTP 401."""
        with pytest.raises(HTTPException) as exc:
            verify_token("not-a-jwt-at-all", token_type="access")
        assert exc.value.status_code == 401


class TestCreateRefreshToken:
    """Tests for create_refresh_token()."""

    def test_returns_encoded_jwt_string(self):
        """Refresh token is a three-segment JWT string."""
        token = create_refresh_token(subject="user-1")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_refresh_payload_has_refresh_type(self):
        """Refresh tokens carry type='refresh' and the correct subject."""
        token = create_refresh_token(subject="user-1")
        payload = verify_token(token, token_type="refresh")
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-1"

    def test_refresh_token_contains_jti(self):
        """Refresh tokens carry a jti claim for rotation tracking."""
        token = create_refresh_token(subject="user-1")
        payload = verify_token(token, token_type="refresh")
        assert "jti" in payload

    def test_each_refresh_token_has_unique_jti(self):
        """Rotated jti values are essential for refresh-token security."""
        token_a = create_refresh_token("user-1")
        token_b = create_refresh_token("user-1")
        payload_a = verify_token(token_a, token_type="refresh")
        payload_b = verify_token(token_b, token_type="refresh")
        assert payload_a["jti"] != payload_b["jti"]


class TestTokenTypeDistinction:
    """Access and refresh tokens must not be interchangeable."""

    def test_access_and_refresh_tokens_differ(self):
        """Access and refresh tokens produced for the same subject differ."""
        access = create_access_token("user-1", "VIEWER", [])
        refresh = create_refresh_token("user-1")
        assert access != refresh

    def test_access_token_rejected_when_refresh_expected(self):
        """An access token cannot be used where a refresh token is required."""
        access = create_access_token("user-1", "VIEWER", [])
        with pytest.raises(HTTPException) as exc:
            verify_token(access, token_type="refresh")
        assert exc.value.status_code == 401
        assert "token type" in exc.value.detail.lower()

    def test_refresh_token_rejected_when_access_expected(self):
        """A refresh token cannot be used where an access token is required."""
        refresh = create_refresh_token("user-1")
        with pytest.raises(HTTPException) as exc:
            verify_token(refresh, token_type="access")
        assert exc.value.status_code == 401
        assert "token type" in exc.value.detail.lower()
