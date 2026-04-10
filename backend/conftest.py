"""Root-level pytest configuration.

This conftest runs BEFORE ``tests/conftest.py`` and BEFORE any ``app.*``
modules are imported. Its sole responsibility is to redirect the test suite
at a dedicated test database so that tests never pollute the development
database.

Resolution order for the test database URL:

1. ``TEST_DATABASE_URL`` env var (if set) — used verbatim.
2. ``DATABASE_URL`` env var — used verbatim **only** if the database name
   already contains ``test`` (CI case).
3. ``DATABASE_URL`` with the database name suffixed by ``_test`` — local dev
   fallback (e.g. ``hnf1b_phenopackets`` -> ``hnf1b_phenopackets_test``).
4. A sensible localhost default matching ``docker/docker-compose.dev.yml``.

Once resolved, ``DATABASE_URL`` is overwritten in ``os.environ`` so that any
subsequent import of ``app.core.config.settings`` picks up the test DB. A
runtime assertion then refuses to proceed if the resolved URL does not look
like a dedicated test database.

To bootstrap the local test database, run::

    make db-test-init
"""

from __future__ import annotations

import os
from urllib.parse import urlparse, urlunparse

_DEFAULT_TEST_URL = (
    "postgresql+asyncpg://hnf1b_user:hnf1b_pass@localhost:5433/hnf1b_phenopackets_test"
)


def _derive_test_database_url() -> str:
    """Compute the database URL to use for the test suite.

    Never returns the dev database URL — if the resolved URL does not look
    like a test database, we either rewrite it or replace it outright.
    """
    explicit = os.environ.get("TEST_DATABASE_URL")
    if explicit:
        return explicit

    base = os.environ.get("DATABASE_URL")
    if not base:
        return _DEFAULT_TEST_URL

    parsed = urlparse(base)
    db_path = parsed.path.lstrip("/")

    # CI already passes a test DB via DATABASE_URL — honour it unchanged.
    if "test" in db_path.lower():
        return base

    # Local dev fallback: rewrite to a sibling ``_test`` database.
    new_path = f"/{db_path}_test" if db_path else "/hnf1b_phenopackets_test"
    return urlunparse(parsed._replace(path=new_path))


def _ensure_test_database_url() -> None:
    """Install the resolved test DB URL and verify it is safe.

    Called at module import time so that every subsequent ``from app.*``
    import — including the one in ``tests/conftest.py`` — sees the test
    database URL rather than the developer's working database.
    """
    resolved = _derive_test_database_url()

    parsed = urlparse(resolved)
    db_name = parsed.path.lstrip("/").lower()

    # Hard safety rail: the word "test" must appear in the database name.
    # This refuses to run tests against databases like ``hnf1b_phenopackets``
    # which developers may have populated with real data.
    if "test" not in db_name:
        raise RuntimeError(
            "Refusing to run backend tests: resolved DATABASE_URL "
            f"database name {db_name!r} does not contain 'test'. "
            "Set TEST_DATABASE_URL to a dedicated test database "
            "(e.g. hnf1b_phenopackets_test) or run `make db-test-init`."
        )

    os.environ["DATABASE_URL"] = resolved
    # Keep TEST_DATABASE_URL aligned so downstream tooling sees the same value.
    os.environ.setdefault("TEST_DATABASE_URL", resolved)

    # JWT_SECRET is required by app.core.config validation. Provide a
    # deterministic fallback for local test runs that do not copy .env in.
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-local-pytest")
    # Avoid the production admin-password validator tripping during tests.
    os.environ.setdefault("ADMIN_PASSWORD", "TestAdminPass!2026")


_ensure_test_database_url()
