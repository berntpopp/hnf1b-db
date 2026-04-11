"""Wave 5a: Settings must refuse to instantiate with enable_dev_auth=True
outside ENVIRONMENT=development. Mirrors the JWT_SECRET / ADMIN_PASSWORD
fail-fast validators already in config.py.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dev_auth_allowed_in_development():
    s = Settings(
        JWT_SECRET="x" * 32,
        ADMIN_PASSWORD="A" * 20,
        environment="development",
        enable_dev_auth=True,
    )
    assert s.enable_dev_auth is True
    assert s.environment == "development"


def test_dev_auth_refused_in_staging():
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="staging",
            enable_dev_auth=True,
        )


def test_dev_auth_refused_in_production():
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="production",
            enable_dev_auth=True,
        )


def test_default_environment_is_production():
    """Unset env defaults to production — an unset env must never default
    to development (that would defeat the whole purpose of Layer 1)."""
    s = Settings(JWT_SECRET="x" * 32, ADMIN_PASSWORD="A" * 20)
    assert s.environment == "production"
    assert s.enable_dev_auth is False
