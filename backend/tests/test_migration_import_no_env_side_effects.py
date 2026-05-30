"""Importing migration modules must not mutate the process environment.

Regression: ``migration/direct_sheets_to_phenopackets.py`` called
``load_dotenv()`` at module top level, so merely *importing* it wrote the
developer's ``backend/.env`` into ``os.environ``. Because several test modules
import that module, test collection alone leaked dev-only flags such as
``ENABLE_DEV_AUTH=true`` into the process environment — which then contaminated
the production-config validation tests (they construct ``Settings`` and inherit
the leaked flag even with ``_env_file=None``, because the value is now a real
process env var rather than a dotenv entry).

Dotenv loading is a CLI concern and belongs in the script entrypoint, not at
import time. This test pins that invariant by spying on ``dotenv.load_dotenv``
in a fresh interpreter: importing the migration module must not invoke it.
A subprocess is used so the assertion is immune to module caching from earlier
collection, and a self-sufficient env is supplied so the transitive
``app.core.config`` import succeeds without depending on an on-disk ``.env``
(e.g. in CI, which has none).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path


def test_importing_direct_sheets_migration_does_not_call_load_dotenv(
    tmp_path: Path,
) -> None:
    """Importing the migration module must not call load_dotenv() at import time."""
    backend_dir = Path(__file__).resolve().parent.parent

    # Spy on dotenv.load_dotenv BEFORE importing the module. The module binds
    # its name via ``from dotenv import load_dotenv`` during its own import,
    # which runs after this patch, so it picks up the spy. An import-time call
    # flips the flag; a call deferred to main() does not.
    script = textwrap.dedent(
        """
        import sys
        import dotenv

        called = {"at_import": False}
        _orig = dotenv.load_dotenv

        def _spy(*args, **kwargs):
            called["at_import"] = True
            return _orig(*args, **kwargs)

        dotenv.load_dotenv = _spy

        import migration.direct_sheets_to_phenopackets  # noqa: F401

        sys.exit(1 if called["at_import"] else 0)
        """
    )

    # Self-sufficient env so app.core.config's module-level Settings() builds
    # cleanly without reading any on-disk .env (cwd is an empty tmp dir).
    child_env = {
        "PYTHONPATH": str(backend_dir),
        "PATH": "/usr/bin:/bin",
        "JWT_SECRET": "0" * 64,
        "ADMIN_PASSWORD": "TestAdminPass!2026",
        "DATABASE_URL": "postgresql+asyncpg://x:x@localhost:5432/x_test",
        "ENVIRONMENT": "development",
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=child_env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "migration.direct_sheets_to_phenopackets called load_dotenv() at import "
        "time — that mutates os.environ for the whole process and leaks the dev "
        f".env into the test suite. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
