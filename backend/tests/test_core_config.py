"""Tests for backend/app/core/config.py startup validation.

Exercises the field_validators for JWT_SECRET and ADMIN_PASSWORD that
cause the application to fail fast if critical secrets are unset.
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE_ENV = {
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5433/test",
}


class TestJwtSecretValidation:
    """Validate JWT_SECRET field_validator fail-fast behavior."""

    def test_empty_jwt_secret_raises(self, monkeypatch):
        """Empty JWT_SECRET must raise ValidationError."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "")
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "JWT_SECRET" in str(exc_info.value)

    def test_whitespace_jwt_secret_raises(self, monkeypatch):
        """Whitespace-only JWT_SECRET must raise ValidationError."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "   ")
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_valid_jwt_secret_accepted(self, monkeypatch):
        """A non-empty JWT_SECRET must allow Settings to construct."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        s = Settings(_env_file=None)
        assert s.JWT_SECRET == "0" * 64


class TestAdminPasswordValidation:
    """Validate ADMIN_PASSWORD field_validator fail-fast behavior."""

    def test_empty_admin_password_raises(self, monkeypatch):
        """Empty ADMIN_PASSWORD must raise ValidationError."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "")
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)
        assert "ADMIN_PASSWORD" in str(exc_info.value)

    def test_whitespace_admin_password_raises(self, monkeypatch):
        """Whitespace-only ADMIN_PASSWORD must raise ValidationError."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "   ")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)


class TestHpoTermsConfig:
    """Smoke-check HPO terms config accessibility via Settings."""

    def test_hpo_terms_section_accessible(self, monkeypatch):
        """hpo_terms property should expose the YAML HPOTermsConfig model."""
        for k, v in BASE_ENV.items():
            monkeypatch.setenv(k, v)
        monkeypatch.setenv("JWT_SECRET", "0" * 64)
        monkeypatch.setenv("ADMIN_PASSWORD", "validpassword")
        s = Settings(_env_file=None)
        # hpo_terms is exposed as a property that proxies to yaml.hpo_terms
        assert hasattr(s, "hpo_terms")
        # Smoke-check that the config contains expected known HPO constants
        assert isinstance(s.hpo_terms.cakut, list)
        assert "HP:0000003" in s.hpo_terms.cakut
        assert s.hpo_terms.mody == "HP:0004904"
