"""Tests for backend/app/auth/password.py.

Covers: password hashing roundtrip, verification, strength validation,
and error cases. Does not test bcrypt internals (those are library tests).
"""

import pytest

from app.auth.password import (
    get_password_hash,
    validate_password_strength,
    verify_password,
)


class TestPasswordHashing:
    """Tests for get_password_hash and verify_password roundtrip."""

    def test_hash_produces_non_empty_string(self):
        """Hashing returns a non-empty string."""
        hashed = get_password_hash("correcthorsebatterystaple")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_is_not_plaintext(self):
        """Hashed value must differ from the plaintext password."""
        password = "correcthorsebatterystaple"
        hashed = get_password_hash(password)
        assert hashed != password

    def test_verify_accepts_correct_password(self):
        """verify_password returns True for the matching plaintext."""
        password = "correcthorsebatterystaple"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_rejects_wrong_password(self):
        """verify_password returns False for a mismatched plaintext."""
        hashed = get_password_hash("correcthorsebatterystaple")
        assert verify_password("wrong password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Bcrypt salts each hash — two calls produce different output."""
        h1 = get_password_hash("samepassword")
        h2 = get_password_hash("samepassword")
        assert h1 != h2
        # But both verify
        assert verify_password("samepassword", h1)
        assert verify_password("samepassword", h2)

    def test_verify_with_empty_password_returns_false(self):
        """An empty plaintext must not verify against a real hash."""
        hashed = get_password_hash("realpassword")
        assert verify_password("", hashed) is False

    @pytest.mark.parametrize(
        "password",
        [
            "a" * 8,  # minimum realistic length
            "p@ssw0rd!",  # special chars
            "日本語パスワード",  # unicode
            "a" * 72,  # bcrypt's 72-byte limit
        ],
    )
    def test_hash_verify_roundtrip_for_various_inputs(self, password):
        """Hash/verify roundtrip works for edge-case inputs."""
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True


class TestPasswordStrength:
    """Tests for validate_password_strength.

    Raises ValueError if password fails any of: min length, uppercase,
    lowercase, digit, or special character requirements.
    """

    def test_accepts_strong_password(self):
        """A password meeting all requirements does not raise."""
        # Should not raise
        validate_password_strength("StrongP@ssw0rd!")

    @pytest.mark.parametrize(
        ("password", "missing"),
        [
            ("Short1!", "at least"),  # too short
            ("nouppercase1!", "uppercase"),  # no uppercase
            ("NOLOWERCASE1!", "lowercase"),  # no lowercase
            ("NoDigitsHere!", "digit"),  # no digit
            ("NoSpecialChar1", "special"),  # no special char
        ],
    )
    def test_rejects_weak_passwords(self, password, missing):
        """Each missing requirement triggers a ValueError."""
        with pytest.raises(ValueError, match="Password validation failed"):
            validate_password_strength(password)
