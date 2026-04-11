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

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "seed_dev_users.py"


def test_seed_script_refuses_production_env():
    """Running the script with ENVIRONMENT=production exits non-zero.

    The script's model_validator will actually let Settings load since
    enable_dev_auth is not set (default False). The script's OWN
    environment check is what blocks it.
    """
    env = os.environ.copy()
    env["ENVIRONMENT"] = "production"
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
    assert "refuses" in combined or "development" in combined or "production" in combined
