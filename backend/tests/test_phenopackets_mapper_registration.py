"""Regression test for SQLAlchemy ``User`` relationship resolution.

Background
----------
``app/phenopackets/models.py`` declares ``relationship("User", ...)`` on
``Phenopacket``, ``PhenopacketAudit`` and ``PhenopacketRevision`` but imported
``User`` only under ``TYPE_CHECKING``. SQLAlchemy resolves those string names
against the declarative registry at mapper-configuration time (the first ORM
query), so if the mappers were configured before any module that imports
``User`` had loaded, the app raised::

    sqlalchemy.exc.InvalidRequestError: When initializing mapper
    Mapper[Phenopacket(phenopackets)], expression 'User' failed to locate a
    name ('User').

The fix adds a runtime ``from app.models.user import User`` at the bottom of
``models.py`` so loading the phenopacket models always registers ``User``.

Why a subprocess
----------------
The test suite's ``conftest.py`` imports ``User`` for its own fixtures, which
registers the class for the whole pytest process and would mask the bug. To
reproduce the production import order faithfully we configure the mappers in a
*fresh* interpreter that imports only ``app.database`` and the phenopacket
models — never ``User`` directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# backend/ — the directory that makes ``app`` importable.
_BACKEND_DIR = Path(__file__).resolve().parents[1]

# Mirrors the production bootstrap order: app.database is imported early
# (it registers a Session event listener), then the phenopacket models, then
# the first ORM query forces configure_mappers(). Crucially, ``User`` is never
# imported explicitly here.
_SNIPPET = """
import app.database  # noqa: F401
import app.phenopackets.models  # noqa: F401
from sqlalchemy.orm import configure_mappers

configure_mappers()
print("MAPPERS_OK")
"""


def test_phenopacket_mappers_configure_without_explicit_user_import():
    """Configuring mappers must succeed without a prior ``User`` import."""
    proc = subprocess.run(
        [sys.executable, "-c", _SNIPPET],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, (
        "Mapper configuration failed — the 'User' relationship regression is "
        f"back.\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert "MAPPERS_OK" in proc.stdout
    assert "failed to locate a name" not in proc.stderr
