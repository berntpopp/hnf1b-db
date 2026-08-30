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
    """Running the script with ENVIRONMENT=production exits non-zero.

    The script's model_validator will actually let Settings load since
    enable_dev_auth is not set (default False). The script's OWN
    environment check is what blocks it.
    """
    env = os.environ.copy()
    env["ENVIRONMENT"] = environment
    # Must provide the other required env vars so Settings can load
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
    combined = (result.stdout + result.stderr).lower()
    assert (
        "refuses" in combined or "development" in combined or "production" in combined
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
