"""Wave 5a Layer 3: seed_dev_users script refuses to run outside dev.

The script's main purpose is local developer ergonomics — one
command, three fixture users ready to log in via the dev quick-login
endpoint. It must refuse to run in staging or production even if
someone sources a .env file with the wrong ENVIRONMENT.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.seed_dev_users import FIXTURE_USERS

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "seed_dev_users.py"


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_seed_script_refuses_non_development_env(environment: str):
    """The script's own guard refuses a fully valid non-development config.

    Staging and production Settings have independent secure-cookie and SMTP
    requirements. Satisfy those here so an earlier Settings validator cannot
    mask the seed script's separate environment guard.
    """
    env = os.environ.copy()
    env["ENVIRONMENT"] = environment
    env["AUTH_COOKIE_SECURE"] = "true"
    env["EMAIL_BACKEND"] = "smtp"
    env["SMTP_HOST"] = "smtp.example.test"
    env["SMTP_USERNAME"] = "test-user"
    env["SMTP_PASSWORD"] = "test-password"
    env["ALLOW_REDIS_FALLBACK"] = "false"
    env.setdefault("JWT_SECRET", "x" * 32)
    env.setdefault("ADMIN_PASSWORD", "A" * 20)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, (
        f"Expected non-zero exit, got {result.returncode}. "
        f"stdout: {result.stdout!r}, stderr: {result.stderr!r}"
    )
    assert result.stderr.strip() == (
        "seed_dev_users refuses to run outside development "
        f"(ENVIRONMENT={environment!r})"
    )


def test_fixture_specs_define_two_distinct_active_verified_curators() -> None:
    """Development fixtures cannot collapse author and reviewer identities."""
    fixtures = {spec["username"]: spec for spec in FIXTURE_USERS}
    curator_a = fixtures["dev-curator-a"]
    curator_b = fixtures["dev-curator-b"]

    assert curator_a["role"] == curator_b["role"] == "curator"
    assert curator_a["is_active"] is curator_b["is_active"] is True
    assert curator_a["is_verified"] is curator_b["is_verified"] is True
    assert curator_a["is_fixture_user"] is curator_b["is_fixture_user"] is True
    assert curator_a["email"] != curator_b["email"]
    assert curator_a["password"] != curator_b["password"]


def test_fixture_specs_keep_a_distinct_active_verified_admin() -> None:
    """The deterministic publisher fixture remains a real admin principal."""
    fixtures = {spec["username"]: spec for spec in FIXTURE_USERS}
    admin = fixtures["dev-admin"]

    assert admin["role"] == "admin"
    assert admin["is_active"] is True
    assert admin["is_verified"] is True
    assert admin["is_fixture_user"] is True
    assert admin["username"] not in {"dev-curator-a", "dev-curator-b"}
