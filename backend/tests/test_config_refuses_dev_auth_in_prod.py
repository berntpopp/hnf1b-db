"""Wave 5a: Settings must refuse to instantiate with enable_dev_auth=True
outside ENVIRONMENT=development. Mirrors the JWT_SECRET / ADMIN_PASSWORD
fail-fast validators already in config.py.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_dev_auth_allowed_in_development():
    """enable_dev_auth=True is the one permitted combo when env=development."""
    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        JWT_SECRET="x" * 32,
        ADMIN_PASSWORD="A" * 20,
        environment="development",
        enable_dev_auth=True,
    )
    assert s.enable_dev_auth is True
    assert s.environment == "development"


def test_dev_auth_refused_in_staging():
    """Staging is not development — Layer 1 must reject the combination."""
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="staging",
            enable_dev_auth=True,
        )


def test_dev_auth_refused_in_production():
    """Production must reject dev-auth regardless of any other config."""
    with pytest.raises(ValidationError, match="ENABLE_DEV_AUTH"):
        Settings(
            _env_file=None,  # type: ignore[call-arg]
            JWT_SECRET="x" * 32,
            ADMIN_PASSWORD="A" * 20,
            environment="production",
            enable_dev_auth=True,
        )


def test_default_environment_is_production(monkeypatch):
    """Unset env defaults to production.

    An unset env must never default to development (that would defeat
    the whole purpose of Layer 1). We explicitly clear both env vars and
    pass ``_env_file=None`` to the constructor so neither the process
    environment nor the on-disk ``backend/.env`` file can contaminate the
    assertion — this test is about the *class default*, not the runtime
    value on any particular developer's machine.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENABLE_DEV_AUTH", raising=False)

    s = Settings(
        _env_file=None,  # type: ignore[call-arg]
        JWT_SECRET="x" * 32,
        ADMIN_PASSWORD="A" * 20,
    )
    assert s.environment == "production"
    assert s.enable_dev_auth is False
